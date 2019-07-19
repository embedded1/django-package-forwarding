from oscar.apps.order.utils import OrderCreator as CoreOrderCreator
from oscar.apps.order.models import BillingAddress
from oscar.apps.address.models import Country
from django.db.models import get_model
from django.utils.encoding import smart_str
from oscar.core.loading import get_class
from oscar.apps.voucher.models import VoucherApplication
from apps.user.models import AccountStatus
from apps.rewards.models import ReferralReward
from operator import attrgetter
from paypal.adaptive.facade import refund_transaction
from apps.user import alerts
from datetime import datetime, timedelta
from django.utils.translation import ugettext_lazy as _
from django.db.models import Count, Avg
from apps.customer.alerts import senders
from django.db.models import Q
from paypal.ipn.models import PaymentMessage
from django.conf import settings
from apps.checkout import cache
from decimal import Decimal as D, InvalidOperation
from paypal import exceptions
import logging
import requests
import pyminfraud

logger = logging.getLogger("management_commands")
Order = get_model('order', 'Order')
OrderNote = get_model('order', 'OrderNote')
Product = get_model('catalogue', 'Product')
Profile = get_model('user', 'Profile')
Basket = get_model('basket', 'Basket')
order_confirmed = get_class('order.signals', 'order_confirmed')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')


class OrderCreator(CoreOrderCreator):
    def create_line_models(self, order, basket_line, extra_line_fields=None):
        """
        Set basket line position to keep fees order in place
        """
        extra_line_fields = {'position': basket_line.position}
        return super(OrderCreator, self).create_line_models(
            order,
            basket_line,
            extra_line_fields=extra_line_fields
        )

    def process_successful_order(self, order):
        """
        This is the main gate for successful orders = orders that were passed
        all IPN validations, we pick some analytics data and record all discounts it contains
        """
        #order completed successfully, the next step is either generating label
        #or wait for download of the prepaid return label
        if order.is_prepaid_return_to_store():
            status = 'Wait for return label download'
        else:
            status = 'In process'

        # Send signal for analytics to pick up
        order_confirmed.send(sender=self, order=order)

        return status


class OrderValidator(object):
    icount_ipn_url = 'https://api.icount.co.il/paypal/ipn.php?iCount=739V09nX0bVrFVJmLIYn7g=='
    BILLING_COUNTRY_MISMATCH, BILLING_NAME_MISMATCH, \
    HIGH_RISK_SCORE, USER_BEHIND_PROXY, \
    ORDER_AMOUNT_OR_CURRENCY_MISMATCH, \
    ORDER_TOTAL_EXCEEDS_FRAUD_THRESHOLD, \
    SHARED_BILLING, SHARED_SHIPPING = (
         'Billing country mismatch',
         'Billing name mismatch',
         'High MaxMind risk score',
         'User registered behind proxy',
         'Order total or currency mismatch',
         'Order total exceeds fraud threshold',
         'Billing name and country does not belong to only 1 customer',
         'Shipping address does not belong to only 1 customer')

    def validate_order_fraud_threshold(self, order):
        """
        we would like to manually inspect every order that exceeds the
        ORDER_FRAUD_THRESHOLD value
        """
        order_fraud_threshold = getattr(settings, 'ORDER_FRAUD_THRESHOLD', '150.0')
        return not (order.total_incl_tax > D(order_fraud_threshold))

    def validate_risk_score(self, order):
        """
        check maxmind risk score to decide if order needs manual fraud inspection
        """
        return not (D(order.risk_score) > D(settings.MINFRAUD_ACCEPT_RISK_SCORE))

    def validate_order_amount_and_currency(self, order_total, order_currency, data_total, data_currency):
        return order_total <= D(data_total) and order_currency == data_currency

    def validate_billing_name(self, order):
        """
        We require that the name of billing will match the account holder name
        To reduce lots of noise we will match only the first 3 characters
        """
        account_first_name = order.user.first_name.decode('utf-8').strip().lower()
        account_last_name = order.user.last_name.decode('utf-8').strip().lower()
        billing_first_name = order.billing_address.first_name.decode('utf-8').strip().lower()
        billing_last_name = order.billing_address.last_name.decode('utf-8').strip().lower()

        #first try to match first 5 characters
        if account_first_name.split(" ", 1)[0][:5] == billing_first_name.split(" ", 1)[0][:5] and \
           account_last_name.split(" ", 1)[0][:5] == billing_last_name.split(" ", 1)[0][:5]:
            return True

        #next check if billing name contains account name
        return account_first_name in billing_first_name and \
            account_last_name in billing_last_name


    def validate_billing_country(self, order):
        """
        We save unlisted countries in line2, we treat such countries as suspicious countries
        Here we validate that the billing country matches the shipping country
        """
        billing_country_code = order.billing_address.country.iso_3166_1_a3 \
            if order.billing_address.line2 is None else None
        shipping_country_code = order.shipping_address.country.iso_3166_1_a3

        #We fail the this validation if we found unlisted country
        if billing_country_code is None:
            return False

        return billing_country_code.lower() == shipping_country_code.lower()


    def validate_unique_billing_details(self, order):
        """
        Here we make sure the billing name and country belong only to 1 user
        We exclude all orders placed by the current order user and check if other
        orders with the current billing details exist, if such orders exist we return False
        otherwise, we return True
        """
        try:
            Order.objects\
                .exclude(Q(status='Cancelled') | Q(user=order.user))\
                .get(billing_address__first_name__iexact=order.billing_address.first_name,
                     billing_address__last_name__iexact=order.billing_address.last_name,
                     billing_address__country__iso_3166_1_a2=order.billing_address.country.iso_3166_1_a2)
        except (Order.DoesNotExist, AttributeError):
            return True
        except Order.MultipleObjectsReturned:
            pass
        return False

    def validate_unique_shipping_address(self, order):
        """
        Here we make sure the shipping address belong only to 1 user
        We exclude all orders placed by the current order user and check if other
        orders with the current billing details exist, if such orders exist we return False
        otherwise, we return True
        """
        try:
            Order.objects\
                .exclude(Q(status='Cancelled') | Q(user=order.user))\
                .get(shipping_address__first_name__iexact=order.shipping_address.first_name,
                     shipping_address__last_name__iexact=order.shipping_address.last_name,
                     shipping_address__line1__iexact=order.shipping_address.line1,
                     shipping_address__line4__iexact=order.shipping_address.line4,
                     shipping_address__postcode__iexact=order.shipping_address.last_name,
                     shipping_address__country__iso_3166_1_a2=order.shipping_address.country.iso_3166_1_a2)
        except (Order.DoesNotExist, AttributeError):
            return True
        except Order.MultipleObjectsReturned:
            pass
        return False

    def return_cancelled_order_referral_credit(self, order):
        """
        This function returns back the referral credit for cancelled orders
        """
        ReferralReward.objects\
            .filter(order=order,
                    is_active=True,
                    date_redeemed__isnull=False)\
            .update(date_redeemed=None)

    def make_package_delivery_reward_inactive(self, order):
        #make package delivery reward that was given for that order inactive
        #as the order is not going to be mailed out
        ReferralReward.objects\
            .filter(order=order, type=ReferralReward.PACKAGE_DELIVERY)\
            .update(is_active=False)

    def remove_vouchers_off_cancelled_order(self, order):
        VoucherApplication.objects.filter(order=order).delete()

    def cancel_order(self, order, cancelled_reason, suspend_account, refund_given=False, **kwargs):
        logger.info("Order is going to be cancelled, reason: %s" % unicode(cancelled_reason))
        account_inactive = False
        payment_source_type = order.get_payment_source_type()

        if payment_source_type == "PayPal":
            pay_key = kwargs.get('key')
            is_echeck = kwargs.get('is_echeck', False)

            if not is_echeck:
                #issue full refund for cancelled orders
                if  not self.refund_order(pay_key):
                    logger.critical("Full refund of order #%s failed" % order.number)
                else:
                    #update refund in source object
                    order.sources.all().update(amount_refunded=order.total_incl_tax)

        #Readd package back to user control panel if we successfully refunded the order
        package = order.package
        package.status = 'pending'
        package.save()

        if suspend_account:
            #suspend user account
            account_inactive = self.suspend_user_account(order.user)

        #return referral credit back to the user
        self.return_cancelled_order_referral_credit(order)
        self.make_package_delivery_reward_inactive(order)
        #remove all vouchers
        self.remove_vouchers_off_cancelled_order(order)
        #save cancelling reason in order note
        OrderNote.objects.create(
            order=order,
            user=order.user,
            note_type='System',
            message=unicode(cancelled_reason),
        )
        #send cancelled order email to user
        senders.send_order_cancelled_email(
            order=order,
            cancelled_reason=cancelled_reason,
            suspend_account=suspend_account,
            account_inactive=account_inactive,
            refund_given=refund_given,
            refund_url=kwargs.get('refund_url'))

    def create_billing_address(self, data):
        country_code = data['residence_country']
        try:
            country = Country.objects.get(iso_3166_1_a2=country_code)
            line2 = None
        except Country.DoesNotExist:
            #fallback to US and add country name in line2
            country = Country.objects.get(iso_3166_1_a2='US')
            line2 = country_code
            logger.error("Found new billing address country: %s" % country_code)

        billing_kwargs = {
            'first_name': data['first_name'],
            'last_name': data['last_name'],
            'line1': data.get('address_street', 'prepaid return label'),
            'line2': line2,
            'line4': data.get('address_city'),
            'postcode': data.get('address_zip'),
            'state': data.get('address_state'),
            'country': country
        }

        obj, _ = BillingAddress.objects.get_or_create(**billing_kwargs)
        return obj

    def get_maxmind_risk_score_and_id(self, order):
        minfraud = pyminfraud.Client(settings.MINFRAUD_LICENSE_KEY)
        risk_score = D('100.0')
        id = None
        #get and delete request related data from cache
        ip, user_agent, accept_language = cache.get_maxmind_data(key=order.number)

        if ip is None:
            logger.critical("We couldn't get IP address of user who placed order #%s" % order.number)
            #special case for dev env, to get passed this validation
            if settings.DEBUG:
                return 0, None
            return risk_score, id

        #dirty hack to bypass the validation for the IP field which raises a weird exception
        minfraud.validate = False
        minfraud.add_field('ip', ip)
        minfraud.validate = True

        minfraud.add_field('user_email', order.user.email)
        minfraud.add_field('user_domain', order.user.email.split('@')[-1])
        minfraud.add_field('transaction_currency', 'USD')

        if user_agent:
            minfraud.add_field('session_useragent', user_agent)

        if accept_language:
            minfraud.add_field('session_language', accept_language)

        if order.shipping_address is not None:
            shipping = {
                'shipping_address': smart_str(order.shipping_address.line1.replace("\"", "")),
                'shipping_city': smart_str(order.shipping_address.city),
                'shipping_zip': order.shipping_address.postcode,
                'shipping_country': order.shipping_address.country.iso_3166_1_a2,
            }
            minfraud.add_fields(shipping)

            if order.shipping_address.state:
                minfraud.add_field('shipping_state', smart_str(order.shipping_address.state))
            if order.shipping_address.phone_number:
                minfraud.add_field('user_phone', order.shipping_address.phone_number.as_international)

        #take billing address, currently we only have first and last names and country
        #we disable it for now as it doesn't tell much
        billing = order.billing_address
        if billing is not None:
            billing = {
                #'billing_city': order.billing_address.city,
                #'billing_state': order.billing_address.state or '',
                #'billing_zip': order.billing_address.postcode,
                'billing_country': order.billing_address.country.iso_3166_1_a2
            }
            minfraud.add_fields(billing)

        try:
            result = minfraud.execute()
        except Exception, e:
            logger.critical("minfraud execute call failed for order #%s, msg = %s" % (order.number, str(e)))
            return risk_score, id
        try:
            risk_score = D(result['riskScore'])
            id = result['maxmindID']
        except InvalidOperation:
            logger.critical("Something bad returned, riskScore = %s" % result['riskScore'])
        except KeyError:
            #we consider exception as fraud order
            #we should not get in here
            logger.critical("We couldn't get maxMind risk score for order #%s" % order.number)
        return risk_score, id

    def get_maxmind_risk_score_and_tran_id(self, order):
        #we mark pre-paid return label orders as legit orders as we will review the return label
        #manually before shipping it
        is_minfraud_enabled =  getattr(settings, 'MINFRAUD_ENABLED', False)
        if is_minfraud_enabled:
            return self.get_maxmind_risk_score_and_id(order)
        return 0, None

    def validate_order(self, order, **kwargs):
        """
        We run the order through some validations tests, order moves to In process status
        if and only if it passes ALL tests
        """

        # Change package status to paid to remove it from the user's control panel
        # only once to avoid
        if order.status == settings.OSCAR_INITIAL_ORDER_STATUS:
            package = order.package
            package.status = 'paid'
            package.save()

        data = kwargs.get('data', None)
        payment_source_type = order.get_payment_source_type()
        if payment_source_type == settings.BITS_OF_GOLD_LABEL:
            #check transaction status
            txn_status = data['status']
            if txn_status == 'paid':
                order.risk_score, order.maxmind_trans_id = self.get_maxmind_risk_score_and_tran_id(order)
                #make sure we received the total amount
                #if payment_source.balance <= 0:
                logger.info("Bitcoin payment completed successfully!")
                status = OrderCreator().process_successful_order(order)
                order.set_status(status)
            elif txn_status == 'expired':
                order.set_status('Cancelled')
                cancelled_reason = _("the Bitcoin transaction didn't complete on time.")
                self.cancel_order(
                    order=order,
                    cancelled_reason=cancelled_reason,
                    suspend_account=False)
            else:
                order.set_status('Cancelled')
                cancelled_reason = _("something went terribly wrong, please contact customer support.")
                self.cancel_order(
                    order=order,
                    cancelled_reason=cancelled_reason,
                    suspend_account=False)
        elif payment_source_type == settings.BITCOIN_PAY_LABEL:
            #check transaction status
            txn_status = data['status']
            if txn_status == 'confirmed':
                order.risk_score, order.maxmind_trans_id = self.get_maxmind_risk_score_and_tran_id(order)
                #make sure we received the total amount
                #if payment_source.balance <= 0:
                logger.info("Bitcoin payment completed successfully!")
                status = OrderCreator().process_successful_order(order)
                order.set_status(status)
            elif txn_status == 'timeout':
                order.set_status('Cancelled')
                cancelled_reason = _("the Bitcoin transaction didn't complete on time.")
                self.cancel_order(
                    order=order,
                    cancelled_reason=cancelled_reason,
                    suspend_account=False)
            elif txn_status == 'insufficient_amount':
                order.set_status('Cancelled')
                cancelled_reason = _("the amount lower than required was sent.")
                self.cancel_order(
                    order=order,
                    cancelled_reason=cancelled_reason,
                    suspend_account=False,
                    refund_url=data.get('payment_url'))
            elif txn_status == 'paid_after_timeout':
                order.set_status('Cancelled')
                cancelled_reason = _("the amount has been paid too late.")
                self.cancel_order(
                    order=order,
                    cancelled_reason=cancelled_reason,
                    suspend_account=False,
                    refund_url=data.get('payment_url'))
            elif txn_status == 'invalid':
                order.set_status('Cancelled')
                cancelled_reason = _("something went terribly wrong, please contact customer support.")
                self.cancel_order(
                    order=order,
                    cancelled_reason=cancelled_reason,
                    suspend_account=False)
            else:
                logger.info("BitcoinPay: got transaction status: %s", txn_status)
        #PAYPAL
        else:
            skip_validation = kwargs.get('skip_validation', False)
            pay_key = kwargs.get('key', None)
            err_msg = ''

            #get risk score and billing address
            order.risk_score, order.maxmind_trans_id = self.get_maxmind_risk_score_and_tran_id(order)
            if data:
                order.billing_address = self.create_billing_address(data)

            if not skip_validation:
                order_validated, err_msg = self.run_validation_tests(order, data)
                if not order_validated:
                    #first check for billing errors
                    if self.cancel_order_required(err_msg):
                        logger.critical("order #%s cancelled: %s" % (order.number, err_msg))
                        #cancel the order issue full refund
                        #and change package status to 'Pending' for the user to re place the order when the order saves
                        status = 'Cancelled'
                    else:
                        profile = order.user.get_profile()
                        #first check if user was registered behind proxy,
                        #we must first clear this before we can continue
                        if err_msg == self.USER_BEHIND_PROXY and profile.user_manually_verified():
                            logger.error("We forgot to update proxy data for user: %s" % order.user.email)
                            status = 'Pending fraud check'
                        #if user isn't manually verified we need to collect some documents
                        elif not profile.user_manually_verified():
                            #the default status is unverified, the user needs to complete
                            #the verification process before he can release his packages for delivery
                            account_status, created = AccountStatus.objects.get_or_create(profile=profile)
                            if created:
                                senders.send_account_verification_email(order.user, account_status.pk)
                            status = 'Pending fraud check'
                        #we already received and reviewed the documents, no need to hold back the order
                        else:
                            status = OrderCreator().process_successful_order(order)
                else:
                    status = OrderCreator().process_successful_order(order)
            else:
                status = OrderCreator().process_successful_order(order)

            #set order's status and save into DB
            order.set_status(status)

            #First, send order emails
            if order.status == 'Cancelled':
                #currently, we cancel order in 2 case: high risk score
                #or order total or currency mismatch
                suspend_account = True
                if err_msg == self.ORDER_AMOUNT_OR_CURRENCY_MISMATCH:
                    cancelled_reason = _("USendHome order processing system suspects that the order"
                                         " has been tampered with illegally.")
                else:
                    cancelled_reason = _("We can't process your payment at the moment.")
                self.cancel_order(
                    order=order,
                    key=pay_key,
                    cancelled_reason=cancelled_reason,
                    suspend_account=suspend_account,
                    refund_given=True)
            elif order.status == 'Pending fraud check':
                logger.info("Order needs to be manually reviewed, reason: %s" % err_msg)
                #mail admins to let them know that a fraud validation is required
                alerts.send_fraud_order_alert(order, err_msg)
            else:
                logger.info("PayPal payment completed successfully!")
                if not settings.DEBUG:
                    if data is None:
                        #need to retrieve IPN message from db
                        try:
                            ipn_message = PaymentMessage.objects.get(pay_key=pay_key)
                        except PaymentMessage.DoesNotExist:
                            logger.error("Couldn't get ipn data from db")
                            return
                        data = ipn_message.context
                    #forward the request to icount to generate receipt
                    requests.post(self.icount_ipn_url, data=data)

    def run_validation_tests(self, order, data):
        if data is not None and \
           not self.validate_order_amount_and_currency(order.total_incl_tax, order.currency,
                                                       data['mc_gross'], data['mc_currency']):
            return False, self.ORDER_AMOUNT_OR_CURRENCY_MISMATCH
        #if not self.validate_billing_name(order):
        #    return False, self.BILLING_NAME_MISMATCH
        if not self.validate_risk_score(order):
            return False, self.HIGH_RISK_SCORE
        #if order.user.get_profile().registered_behind_proxy():
        #    return False, self.USER_BEHIND_PROXY
        #if not self.validate_billing_country(order):
        #    return False, self.BILLING_COUNTRY_MISMATCH
        if not self.validate_unique_billing_details(order):
            return False, self.SHARED_BILLING
        if not self.validate_unique_shipping_address(order):
            return False, self.SHARED_SHIPPING
        #if not self.validate_order_fraud_threshold(order):
        #    return False, self.ORDER_TOTAL_EXCEEDS_FRAUD_THRESHOLD
        return True, None

    def auth_docs_required(self, err_msg):
        return err_msg in [
            self.HIGH_RISK_SCORE, self.USER_BEHIND_PROXY,
            self.ORDER_TOTAL_EXCEEDS_FRAUD_THRESHOLD]

    def cancel_order_required(self, err_msg):
        return err_msg in [
            self.BILLING_COUNTRY_MISMATCH,
            self.BILLING_NAME_MISMATCH,
            self.ORDER_AMOUNT_OR_CURRENCY_MISMATCH,
            self.SHARED_BILLING,
            self.SHARED_SHIPPING]

    @staticmethod
    def refund_order(pay_key):
        """
        issue full refund for cancelled orders
        returns True if refund succeeded else False
        """
        logger.info("Issuing full refund to cancelled order")
        try:
            refund_transaction(pay_key)
        except exceptions.PayPalError:
            return False
        return True

    @staticmethod
    def suspend_user_account(user):
        """
        We make user's account inactive if he has no package in store
        Otherwise, we just make sure the only operation he can take is to return his
        in store packages back to the senders
        We return True if account is inactive, otherwise we return False
        """
        in_store_packages = Product.in_store_packages.filter(owner=user)
        if in_store_packages.exists():
            in_store_packages.update(status='pending')
            return False

        user.is_active = False
        user.save()
        return True


def orders_ready_for_delivery(orders):
    ready_orders = []
    users_data = {}
    for order in orders:
        key = order.user_id
        if 'orders' in users_data.get(key, {}):
            users_data[key]['orders'].append(order)
        else:
            users_data[key] = {'user': order.user, 'orders': [order]}

    for key, val in users_data.iteritems():
        time_threshold = None
        user = val['user']
        orders = sorted(val['orders'], key=attrgetter('date_placed'))

        # fast lane for specific users
        if user.id in settings.USERS_EXCLUDED_DISPATCH_DELAY:
            ready_orders.extend(orders)
            continue

        last_order = orders[-1]
        data = user.orders\
            .exclude(status__in=['Cancelled', 'Refunded', 'Pending'])\
            .aggregate(avg_risk_score=Avg('risk_score'), order_count=Count('id'))
        order_count = data['order_count']
        avg_risk_Score = data['avg_risk_score']

        #check for average risk score, we don't hold on to orders with low risk score
        if avg_risk_Score > 5.0:
            # first time order = hold for 1 day
            if order_count == 1:
                time_threshold = datetime.now() - timedelta(days=1)
            # order 2-3 = hold for 12 hours
            elif 1 < order_count < 4:
                time_threshold = datetime.now() - timedelta(hours=12)
        if not time_threshold or last_order.date_placed < time_threshold:
            ready_orders.extend(orders)

    return ready_orders
