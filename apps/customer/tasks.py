from __future__ import absolute_import
from packageshop.celery import app
from apps.basket.models import Basket
from apps.order.models import Order
#from celery.five import monotonic
from django.contrib.auth.models import User
from apps.customer.alerts import senders
from django.core.cache import cache
from contextlib import contextmanager
from apps.user import tokens
from django.conf import settings
from mailchimp3 import MailChimp
from google_measurement_protocol import Item, report, Transaction
from prices import Price
import analytics

import logging

logger = logging.getLogger("management_commands")

if settings.DEBUG:
    analytics.write_key = '9X11rRPGu1DnnfNzw63PfUnLXTkSUiLo'
else:
    analytics.write_key = '7cXnTOvheZH371DARxUrUOHl2Tag0GHX'

@app.task(ignore_result=True)
def mixpanel_post_registration(mixpanel_anon_id, user, profile, backend,
                               referrer_mailbox, register_type, **kwargs):
    if mixpanel_anon_id:
        data = {
            'createdAt': user.date_joined,
            'email': user.email,
            'firstName': user.first_name,
            'lastName': user.last_name,
            'type': register_type,
        }

        if referrer_mailbox:
            data['referrer_mailbox'] = referrer_mailbox
            data['referrer_name'] = kwargs.pop('referrer_name', '')
        if profile.ip:
             data['ip'] = profile.ip
        if kwargs:
            data.update(kwargs)

        analytics.alias(mixpanel_anon_id, user.id)
        analytics.flush()
        analytics.identify(mixpanel_anon_id, data)

        if profile.registration_type.lower() == 'purse':
            analytics.track(mixpanel_anon_id, 'Account Created Via Purse', {
                'authentication': backend,
            })
        else:
            analytics.track(mixpanel_anon_id, 'Account Created', {
                'authentication': backend,
            })

        # users coming through our API can have their email address confirmed before reaching to this
        # code so we need to trigger the Email Confirmed event if email was already confirmed
        if profile.email_confirmed:
            analytics.track(mixpanel_anon_id, 'Email Confirmed')

@app.task(ignore_result=True)
def mixpanel_track_sent_package(package, extra_services, partner_name, additional_receiver):
    data =  {
        'merchant': package.title,
        'SentOutsideUs': package.is_sent_outside_usa,
        'containsProhibitedItems': package.is_contain_prohibited_items,
        'condition': package.condition,
        'additionalReceiver': additional_receiver is not None,
        'logisticsPartner': partner_name,
        'packageConsolidation': package.owner.get_profile().is_consolidate_every_new_package,
        'weight': package.weight,
        'height': package.height,
        'length': package.length,
        'width': package.width
    }

    if extra_services:
        data.update({
            'special_requests': {
                'customsPaperwork': extra_services.is_filling_customs_declaration,
                'repacking': extra_services.is_repackaging,
                'expressCheckout': extra_services.is_express_checkout,
                'removeInvoice': extra_services.is_remove_invoice,
                'extraProtection': extra_services.is_extra_protection,
                'photosCount': extra_services.get_number_of_photos(),
                'customRequests': extra_services.is_custom_requests
            }
        })

    analytics.track(package.owner.id, 'Sent Package', data)

@app.task(ignore_result=True)
def mixpanel_track_academy_extra_service_order(user_id, service):
    analytics.track(user_id, 'Academy Extra Service Order', {'extra_service': service})

@app.task(ignore_result=True)
def mixpanel_track_completed_order(order_id):
    def get_coupons(basket):
        return ' '.join(basket.grouped_voucher_discounts)

    def get_products(order):
        products = []
        for line in order.lines.all():
            products.append({
                'id': line.id,
                'title': line.description,
                'quantity': line.quantity,
                'price': str(line.line_price_incl_tax),
            })
        return products

    try:
        order = Order.objects\
            .select_related('package', 'user', 'user__profile')\
            .prefetch_related('sources')\
            .get(id=order_id)
    except Order.DoesNotExist:
        logger.error("mixpanel_track_completed_order: order %s does not exist", order_id)
        return

    #don't record cancelled, Pending or refunded orders
    if order.status in ['Pending', 'Cancelled', 'Refunded']:
        return

    basket = Basket.objects.get(id=order.basket_id)
    source = order.sources.all()[0]
    package = order.package
    analytics.track(order.user.id, 'Completed Order', {
        'orderNumber': order.number,
        'orderId': order.id,
        'total': str(order.total_incl_tax),
        'revenue': str(source.self_revenue()),
        'carrier': order.tracking.carrier,
        'shippingMethod': order.shipping_method,
        'shippingMargin': str(order.shipping_margin()),
        'shippingInsuranceMargin': str(order.shipping_insurance_margin()),
        'discount': str(order.total_discount_incl_tax),
        'coupon': get_coupons(basket),
        'UserOrigin': order.user.get_profile().registration_type,
        'paymentMethod': source.label,
        'consolidatedPackage': package.is_consolidated,
        'daysInStorage': package.get_storage_days(),
        'postConsolidationDeliveryDays': package.get_post_consolidation_days(),
        'products': get_products(order)
    })

@app.task(ignore_result=True)
def ga_track_completed_order(order_id):
    def get_items(order):
        items = []
        for line in order.lines.all():
            items.append(
                Item(
                    name=line.description,
                    unit_price=Price(line.line_price_incl_tax, currency='USD'),
                    quantity=line.quantity,
                    item_id=line.id
                )
            )
        return items

    try:
        order = Order.objects\
            .select_related('package', 'user', 'user__profile')\
            .prefetch_related('sources')\
            .get(id=order_id)
    except Order.DoesNotExist:
        logger.error("ga_track_completed_order: order %s does not exist", order_id)
        return

    #don't record cancelled, Pending or refunded orders
    if order.status in ['Pending', 'Cancelled', 'Refunded']:
        return

    #check if we have client id to identify the transaction
    ga_client_id = order.ga_client_id
    if not ga_client_id:
        logger.error("ga_track_completed_order: order %s does not contain ga client id", order_id)
        return

    try:
        source = order.get_payment_source()
        transaction_id = order.number
        transaction = Transaction(
            transaction_id=transaction_id,
            items=get_items(order),
            revenue=Price(source.self_revenue(), currency='USD'),
            shipping=Price(order.shipping_incl_tax, currency='USD'),
            affiliation=order.user.get_profile().registration_type
        )
        report(settings.GOOGLE_ANALYTICS_ID, ga_client_id, transaction)
    except Exception:
        logger.exception("Exception in ga_track_completed_order")

@app.task(ignore_result=True)
def mixpanel_track_user_invited(user_id, invitee_emails, invite_type):
    for invitee_email in invitee_emails:
        analytics.track(user_id, 'User Invited', {
            'inviteeEmail': invitee_email,
            'inviteType': invite_type
        })

@app.task(ignore_result=True)
def mixpanel_track_calculator(user_id, event_type, calculator_type, **kwargs):
    if user_id:
        data = {'calculatorType': calculator_type}
        data.update(kwargs)
        analytics.track(user_id, event_type, data)

@app.task(ignore_result=True)
def mixpanel_track_email_confirmation(user_id, **kwargs):
    if user_id:
        analytics.track(user_id, 'Email Confirmed')

@app.task(ignore_result=True)
def mixpanel_track_create_shipping_address(user_id, **kwargs):
    if user_id:
        analytics.track(user_id, 'Shipping Address Created')

@app.task(ignore_result=True)
def subscribe_user(user, list_id, group_settings=None, is_conf_url_required=False):
    #add user to newsletter list
    try:
        client = MailChimp(settings.MAILCHIMP_USERNAME, settings.MAILCHIMP_API_KEY)

        merge_vars = {
            'EMAIL': user.email,
            'FNAME': user.first_name,
            'LNAME': user.last_name,
        }

        if is_conf_url_required:
            merge_vars['CONFURL'] = 'https://usendhome.com{}'.format(
                senders.get_email_confirmation_url(user, tokens.email_confirmation_token_generator))

        kwargs = {
            'email_address': user.email,
            'status_if_new': 'subscribed',
            'merge_fields': merge_vars,
        }
        if group_settings:
            kwargs['interests'] = group_settings

        client.lists.members.create_or_update(list_id, user.email, kwargs)

    except Exception:
        logger.exception("Exception in subscribe_user, user id = %s", user.id)

@app.task(ignore_result=True)
def unsubscribe_user(user, list_id):
    try:
        client = MailChimp(settings.MAILCHIMP_USERNAME, settings.MAILCHIMP_API_KEY)
        client.lists.members.update(list_id, user.email, {'status': 'unsubscribed'})
    except Exception:
        logger.exception("Exception in unsubscribe_user, user id = %s", user.id)

#@app.task(ignore_result=True)
#def unsubscribe_users(users, list_id):
#    try:
#        list = utils.get_connection().get_list_by_id(list_id)
#        list.batch_unsubscribe(
#            emails=[user.email for user in users],
#            delete_member=True,
#            send_goodbye=False,
#            send_notify=False
#        )
#    except Exception:
#        logger.exception("Exception in unsubscribe_users")

@app.task(ignore_result=True)
def send_api_complete_registration_email(user, issuer):
    senders.send_api_complete_registration_email(user, issuer)

LOCK_EXPIRE = 60 * 10  # Lock expires in 10 minutes

@contextmanager
def memcache_lock(lock_id, oid):
    #timeout_at = monotonic() + LOCK_EXPIRE - 3
    # cache.add fails if the key already exists
    status = cache.add(lock_id, oid, LOCK_EXPIRE)
    try:
        yield status
    finally:
        # we don't release the lock as we don't want to let more workers to do
        # the same work as we did, the lock will be released when the timeout expires
        pass
        # memcache delete is very slow, but we have to use it to take
        # advantage of using add() for atomic locking
        #if monotonic() < timeout_at:
        #    # don't release the lock if we exceeded the timeout
        #    # to lessen the chance of releasing an expired lock
        #    # owned by someone else.
        #    cache.delete(lock_id)

@app.task(ignore_result=True)
def send_api_complete_registration_follow_up_email(user_id, issuer):
    lock_id = '{0}-lock-{1}'.format(user_id, issuer)
    with memcache_lock(lock_id, app.oid) as acquired:
        if acquired:
            #fetch user from the DB to get the latest state
            user = User.objects.get(id=user_id)
            profile = user.get_profile()
            #check if user completed setting up their account
            if not profile.is_account_setup_completed:
                senders.send_thirty_minutes_post_api_registration_email(user, issuer)

@app.task(ignore_result=True)
def send_api_email_confirmation_email(user, profile, issuer):
    senders.send_email_confirmation_email(user=user, profile=profile, issuer=issuer)

@app.task(ignore_result=True)
def send_api_thirty_minutes_post_signup_email(user):
    senders.send_thirty_minutes_post_signup_email(user)
