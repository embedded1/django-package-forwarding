from __future__ import absolute_import
from packageshop.celery import app
from apps.shipping.utils import add_shipping_event
import simplejson as json
from apps.order.models import Order
from apps.payment.sources.bitcoin.models import BitsOfGoldPaymentMessage, BitsOfGoldTransaction
from apps.payment.sources.bitcoinpay.models import BitcoinPayPaymentMessage, BitcoinPayTransaction
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils.http import urlencode
from apps.order.utils import OrderValidator
from collections import OrderedDict
from apps.customer.alerts import senders
from paypal.ipn.models import PaymentMessage
from paypal.adaptive.facade import fetch_transaction_details
from paypal import exceptions
from django.core import mail
from django.template import loader, Context
import logging
import hashlib
import requests


logger = logging.getLogger("management_commands")


@app.task(ignore_result=True)
def easypost_tracking_details_handler(data):
    EXCLUDE_STATUS_LIST = ['unknown',]

    def filter_out_tracking_details(tracking_details):
        return filter(lambda x: x['status'].lower() not in EXCLUDE_STATUS_LIST, tracking_details)

    def package_has_status(tracking_details, statuses):
        for tracking_detail in tracking_details:
            for status in statuses:
                if tracking_detail['status'].lower() == status:
                    return True
        return False

    def send_delivery_updates(customer):
        return customer.get_profile().package_tracking

    def delivery_exception_notification(latest_status, order, package):
        ctx = Context({
            'carrier': order.tracking.carrier,
            'tracking_number': order.tracking.tracking_number,
            'package': package,
            'status': latest_status
        })
        subject_tpl = loader.get_template('user/alerts/emails/admins/delivery_exception_subject.txt')
        body_tpl = loader.get_template('user/alerts/emails/admins/delivery_exception_body.txt')
        body_html_tpl = loader.get_template('user/alerts/emails/admins/delivery_exception_body.html')
        mail.mail_admins(
            subject=subject_tpl.render(ctx).strip(),
            message=body_tpl.render(ctx),
            html_message=body_html_tpl.render(ctx)
        )

    logger.info("EasyPost tracker webhook received")
    try:
        event = json.loads(data)
        if event and event['description'] == 'tracker.updated':
            result = event['result']
            shipment_id = result['shipment_id']
            tracking_details = result['tracking_details']
            mode = event['mode']
            status = result['status'].lower()
            #filter out unneeded events
            filtered_tracking_details = filter_out_tracking_details(tracking_details)
            num_of_events = len(filtered_tracking_details)
            #get package that matches the shipment id to mark it as shipped
            if num_of_events > 0:
                try:
                    order = Order.objects\
                        .select_related('user', 'user__profile',
                                        'package', 'tracking')\
                        .get(tracking__shipment_id=shipment_id)
                except Order.DoesNotExist:
                    #in test mode, easypost sends a webhooks requests immedietly after postage purchase
                    #at that stage we may not have easypost shipment id stored in the DB
                    #therefore, we need to filter out logging event in test mode
                    if mode.lower() == "production":
                        logger.critical("EasyPost tracker webhook - no matching order for shipment id: %s,"
                                        " tracking status = %s, " % (shipment_id, status))
                else:
                    logger.info("EasyPost tracker - got tracker.updated event for order: #%s with status: %s"
                                % (order.number, status))

                    #bail out if order is cancelled / refunded
                    if order.status in ('Cancelled', 'Refunded'):
                        return

                    customer = order.user
                    package = order.package

                    #set tracking number if we don't get an hold of it before
                    if not order.tracking.tracking_number:
                        order.tracking.tracking_number = result['tracking_code']
                        order.tracking.save()

                    #save latest status for audit as shipping event
                    latest_tracking_activity = filtered_tracking_details[num_of_events-1]['message']
                    add_shipping_event(order, latest_tracking_activity, event_type_name=status)

                    #if we got here and order isn't marked as shipped
                    #we probably in pre_transit stage where we would like to
                    #notify the customer that his order was shipped
                    if not order.is_shipped():
                        package.status = 'shipped'
                        package.save()
                        try:
                            #change status to shipped and send notification to customer
                            order.set_status('Shipped')
                        except Exception, e:
                            logger.error("Partner payment didn't complete for order number: %s, error = %s",
                                         order.number, e)
                            return

                    #no need to send the pre_transit activity so we bail out here
                    if status == 'pre_transit':
                        return
                    #update order status
                    elif status == 'delivered':
                        order.set_status('Delivered')
                        package.status = 'delivered'
                        package.save()
                    elif status == 'return_to_sender':
                        order.set_status('Return to sender')
                        package.status = 'return_to_sender'
                        package.save()
                    elif status == 'failure':
                        order.set_status('Failure')
                    elif status == 'out_for_delivery':
                        order.set_status('Out for delivery')
                        package.status = 'out_for_delivery'
                        package.save()
                    elif status == 'available_for_pickup':
                        order.set_status('Available for pickup')
                        package.status = 'available_for_pickup'
                        package.save()
                    elif status == 'cancelled':
                        order.set_status('Failure')
                    elif status == 'error':
                        order.set_status('Failure')

                    #don't send shipping updates to inactive user
                    if customer.is_active and (status in ('failure', 'error') or send_delivery_updates(customer)):
                        #send full tracking activity to customer
                        senders.send_tracker_update_alert(
                            order=order,
                            tracking_details=filtered_tracking_details,
                            carrier=order.tracking.carrier,
                            display_carrier=order.tracking.display_carrier,
                            tracking_number=order.tracking.tracking_number,
                            latest_status=status)

                    #send notification to admin if a package is on the way back to us/failure/cancelled/error
                    if package_has_status(filtered_tracking_details, ['return_to_sender', 'failure', 'cancelled', 'error']):
                        delivery_exception_notification(status, order, package)
                        logger.error("EasyPost tracker - delivery exception has occurred for order: #%s, status = %s"
                                     % (order.number, status))
    except json.JSONDecodeError:
        pass
    except Exception, e:
        logger.exception("Easypost tracker exception: %s" % e)


@app.task(ignore_result=True)
def bitcoin_ipn_transaction_handler(raw_message, data):
    def verify_data(data):
        params = [
            ('token', data.get('token', '')),
            ('amount_usd', data.get('amount_usd', '')),
            ('amount_btc', data.get('amount_btc', '')),
            ('userid', data.get('userid', '')),
            ('txid', data.get('txid', '')),
            ('status', data.get('status', ''))
        ]
        param_dict = OrderedDict(params)
        secret = settings.BITS_OF_GOLD_SANDBOX_API_KEY if is_sandbox() else\
            settings.BITS_OF_GOLD_LIVE_API_KEY
        key = urlencode(param_dict) + secret
        return hashlib.sha1(key).hexdigest() == data['checksum']

    def is_sandbox():
        return getattr(settings, 'BITS_OF_GOLD_SANDBOX_MODE', False)

    def process_order(order, data):
       OrderValidator().validate_order(order=order, data=data)

    def save_order_amounts(data):
       BitsOfGoldTransaction.objects\
           .filter(token=data['token'])\
           .update(amount=data['amount_usd'],
                   amount_btc=data['amount_btc'])

    #def save_usd_amount(order, data):
    #    payment_source = order.get_payment_source()
    #    payment_source.amount_debited = data['amount_usd']
    #    payment_source.save()

    def save_payment_ipn_message(raw_message, data):
        #save IPN message into DB
        BitsOfGoldPaymentMessage.objects.create(
            transaction_id=data['txid'],
            raw_message= raw_message,
            payment_status= data['status'],
            is_sandbox= is_sandbox(),
            source=settings.BITS_OF_GOLD_LABEL)

    def get_order(basket_id):
        """
        We need to link this message to an order. this can be done as:
        use a pay_key to locate the order through its payment source
        """
        try:
            return Order.objects.select_related(
                'user', 'package', 'tracking').get(
                basket_id=basket_id)
        except Order.DoesNotExist:
            return None

    logger.info("BitsOfGold IPN webhook received")
    if verify_data(data):
        #we finished with the validations, now its time to process the payment_status data
        save_payment_ipn_message(raw_message, data)
        #save bitcoin and usd amounts into the txn
        save_order_amounts(data)

        basket_id = data['txid']
        order = get_order(basket_id)
        if not order:
            #oops - no such order
            logger.error("Order that belongs to basket_id: %s not found" % basket_id)
            return

        #update debited amount as we may get partial payments
        #save_usd_amount(order, data)
        #payment completed. need to update order status, get billing address,
        #and send order confirmation email
        logger.info("Found matching order #%s" % order.number)
        process_order(order, data)
    else:
        logger.error("Bitcoin IPN: received unverified data")

@app.task(ignore_result=True)
def paypal_ipn_transaction_handler(raw_message, data):
    verify_url = "https://www.paypal.com/cgi-bin/webscr"
    sandbox_verify_url = "https://www.sandbox.paypal.com/cgi-bin/webscr"

    def is_sandbox(data):
        try:
            return bool(int(data['test_ipn']))
        except KeyError:
            return False

    def verify_data(data):
        payload = {
            'cmd': '_notify-validate',
        }
        payload.update(data)
        url = sandbox_verify_url if is_sandbox(data) else verify_url
        response = requests.post(url, payload)
        return response.content == 'VERIFIED'

    def process_order(order, data, pay_key):
        #we update and save order to DB in this function
        OrderValidator().validate_order(order=order, key=pay_key, data=data)

    def validate_recipient(receiver_email):
        return settings.PAYPAL_PRIMARY_RECEIVER_EMAIL == receiver_email

    def is_duplicate_response(data):
        try:
            PaymentMessage.objects.get(
                transaction_id=data['txn_id'],
                payment_status=data['payment_status'])
            return True
        except PaymentMessage.DoesNotExist:
            return False

    def get_tran_pay_key(data):
        """
         Call PaymentDetails with the data['txn_id'] value to get PAY pay_key,
         we can do this as we in completed payment state
        """
        txn_id = data['parent_txn_id'] if 'parent_txn_id' in data else data['txn_id']
        try:
            txn_details = fetch_transaction_details(txn_id)
        except exceptions.PayPalError:
            logger.critical("PaymentDetails API call failed")
            return None
        else:
            return txn_details.pay_key

    def get_order(pay_key):
        """
        We need to link this message to an order. this can be done as:
        use a pay_key to locate the order through its payment source
        """
        try:
            return Order.objects.select_related(
                'user', 'package', 'tracking').get(
                sources__reference=pay_key)
        except Order.DoesNotExist:
            return None

    def collect_fraud_filters(data):
        fraud_filters = []
        template = 'fraud_management_pending_filters_'
        for i in range(1,18):
            fraud_filter = template + str(i)
            if fraud_filter in data:
                fraud_filters.append(data[fraud_filter])
        return ", ".join(fraud_filters)

    def save_payment_ipn_message(raw_message, pay_key, data):
        #save IPN message into DB
        payment_status = data['payment_status']
        #collect fraud filters once when the payment_status is Pending
        if payment_status.lower() == 'pending':
            fraud_management_filters = collect_fraud_filters(data)
        else:
            fraud_management_filters = None
        obj, created = PaymentMessage.objects.get_or_create(
            transaction_id=data['txn_id'],
            defaults={
                'pay_key': pay_key,
                'payment_status': payment_status,
                'fraud_management_filters': fraud_management_filters,
                'raw_message': raw_message,
                'is_sandbox': is_sandbox(data)})
        if not created:
            obj.pay_key = pay_key
            obj.payment_status = payment_status
            obj.fraud_management_filters = fraud_management_filters
            obj.raw_message = raw_message
            obj.is_sandbox = is_sandbox(data)
            obj.save()

    logger.info("PayPal IPN webhook received")

    if verify_data(data):
        if not validate_recipient(data.get('receiver_email', '')):
            logger.error("Invalid receiver found: %s" % data['receiver_email'])
            return

        if is_duplicate_response(data):
            logger.error("Duplicate response found: %s %s" % (data['txn_id'], data['payment_status']))
            return

        #we finished with the validations, now its time to process the payment_status data
        #get pay_key of the original transaction
        pay_key = get_tran_pay_key(data)
        save_payment_ipn_message(raw_message, pay_key, data)

        order = get_order(pay_key)
        if not order:
            #oops - no such order
            logger.error("Order that belongs to pay_key: %s not found" % pay_key)
            return

        payment_status = data.get('payment_status', '').lower()
        payment_type = data.get('payment_type', '').lower()
        is_echeck = payment_type == 'echeck'

        if payment_status == 'completed':
            #payment completed. need to update order status, get billing address,
            #and send order confirmation email
            logger.info("Found matching order #%s" % order.number)
            process_order(order, data, pay_key)
        elif payment_status == 'pending':
            if is_echeck:
                order.set_status('Pending clearance')
                package = order.package
                package.status = 'pending_clearance'
                package.save()
        elif payment_status == 'failed':
            order.set_status('Cancelled')
            cancelled_reason = _("Payment was not processed successfully at the sender's side.")
            OrderValidator().cancel_order(
                order=order,
                cancelled_reason=cancelled_reason,
                suspend_account=False,
                is_echeck=is_echeck
            )
        elif payment_status == 'refunded':
            #payment refunded. need to validate that all refunds
            #went through successfully
            logger.info("Received refund message for order #%s" % order.number)
    else:
        logger.error("PayPal IPN: received unverified data")


@app.task(ignore_result=True)
def bitcoinpay_ipn_transaction_handler(raw_message, data, req_sig):
    def verify_data(data, req_sig):
        key = getattr(settings, 'BITCOIN_PAY_SIGNATURE', '')
        return hashlib.sha256(data + key).hexdigest() == req_sig

    def process_order(order, data):
       OrderValidator().validate_order(order=order, data=data)

    def save_order_amounts(data):
        BitcoinPayTransaction.objects\
           .filter(token=data['payment_id'])\
           .update(amount=data['price'],
                   amount_btc=data['paid_amount'])


    def save_payment_ipn_message(raw_message, data):
        #save IPN message into DB
        BitcoinPayPaymentMessage.objects.create(
            transaction_id=data['payment_id'],
            raw_message=urlencode(json.loads(raw_message)),
            payment_status= data['status'],
            is_sandbox=False,
            source=settings.BITCOIN_PAY_LABEL)

    def get_order(basket_id):
        """
        We need to link this message to an order. this can be done as:
        use a pay_key to locate the order through its payment source
        """
        try:
            return Order.objects.select_related(
                'user', 'package', 'tracking').get(
                basket_id=basket_id)
        except Order.DoesNotExist:
            return None

    def get_transaction_data(payment_id):
        if not payment_id:
            logger.error("payment_id was not found for basket_id = %s", basket_id)
            return None

        url = 'https://www.bitcoinpay.com/api/v1/transaction-history/{}'.format(payment_id)
        headers = {'Content-type': 'application/json', 'Authorization': 'Token {}'.format(settings.BITCOIN_PAY_LIVE_API_KEY)}

        for req_num in range(3):
            response = requests.get(url, headers=headers)
            if response.status_code == requests.codes.ok:
                break

        # req_num == 2 and status_code != OK means that all 3 requests have failed
        if req_num == 2 and response.status_code != requests.codes.ok:
            logger.error("Get transaction details failed, status_code = %s, basket_id = %s",
                         response.status_code, basket_id)
            return None

        return json.loads(response.content)['data']

    try:
        logger.info("Bitcoinpay IPN webhook received")
        if verify_data(raw_message, req_sig):
            #we finished with the validations, now its time to process the payment_status data
            save_payment_ipn_message(raw_message, data)

            basket_id = json.loads(data['reference'])['txid']
            order = get_order(basket_id)
            if not order:
                #oops - no such order
                logger.error("Order that belongs to basket_id: %s not found" % basket_id)
                return

            #update debited amount as we may get partial payments
            #save_usd_amount(order, data)
            #payment completed. need to update order status, get billing address,
            #and send order confirmation email
            logger.info("Found matching order #%s" % order.number)
            status = data['status']
            if status == 'confirmed':
                data = get_transaction_data(data['payment_id'])
                if not data:
                    return
                #save bitcoin and usd amounts into the txn
                save_order_amounts(data)
            # process order
            process_order(order, data)
        else:
            logger.error("Bitcoinpay IPN: received unverified data")
    except Exception, e:
        logger.exception("BitcoinPay webhook handling exception: %s", e)

