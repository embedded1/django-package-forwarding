from apps.user import utils, tokens
from django.core.urlresolvers import reverse
from django.db.models import get_model
from django.utils.translation import ugettext as _
from oscar.core.loading import get_class
from django.utils import simplejson as json
from django.conf import settings
from django.template import Context, loader
from django.utils.http import int_to_base36
from django.core.exceptions import ObjectDoesNotExist
from post_office import mail
from datetime import datetime, timedelta
from apps import utils as app_utils
import logging
import base64

logger = logging.getLogger("management_commands")
CommunicationEventType = get_model('customer', 'communicationeventtype')
CommunicationEvent = get_model('customer', 'communicationevent')
Dispatcher = get_class('customer.utils', 'Dispatcher')
Email = get_model('customer', 'Email')


def send_product_change_status_alert(customer, package, extra_msg):
    """
    Send new package alert email to let the user know we received his package
    Send shipped package alert email to let the user know we shipped his package
    Create email history record
    """
    ctx = {'package': package}

    if package.status == 'pending':
        logger.info("Sending email alert on new package: %s" % package.upc)
        ctx['fulfilled_special_requests'] = package.fulfilled_special_requests_list()
        ctx['customized_services'] = package.get_customized_services()
        ctx['customized_services_brief'] = package.get_customized_services_brief()
        #check if additional receiver exists
        if not package.receiver_verified():
            ctx['additional_receiver'] = package.additional_receiver
        #add email category
        if not settings.DEBUG:
            ctx['headers'] = {'X-SMTPAPI': json.dumps({"category": "Package Received"})}
        communication_type_code = 'PENDING_PACKAGE'
        category = 'Action'
    #elif package.status == 'waiting_for_consolidation':
    #    logger.info("Sending email alert on waiting for consolidation for package: %s" % package.upc)
    #    communication_type_code = 'CONSOLIDATION_REQUIRED'
    #    category = 'Info'
    elif package.status == 'pre_pending':
        logger.info("Sending email alert on missing client id for package: %s" % package.upc)
        upc = settings.MISSING_CLIENT_ID_TEMPLATE % package.upc
        try:
            package.variants.get(upc=upc)
        except ObjectDoesNotExist:
           is_charged  = False
        else:
            is_charged = True
        ctx['is_charged'] = is_charged
        communication_type_code = 'MISSING_CLIENT_ID'
        category = 'Info'
    elif package.status == 'contains_prohibited_items':
        logger.info("Sending email alert on package that contains prohibited items: %s" % package.upc)
        communication_type_code = 'CONTAINS_PROHIBITED_ITEMS'
        ctx['prohibited_items_msg'] = extra_msg
        category = 'Action'
    elif package.status == 'predefined_waiting_for_consolidation':
        logger.info("Sending email alert on predefined waiting for consolidation for package: %s" % package.upc)
        communication_type_code = 'PREDEFINED_CONSOLIDATION_REQUIRED'
        category = 'Info'
    elif package.status == 'consolidation_done':
        logger.info("Sending email alert on consolidation done for package: %s" % package.upc)
        communication_type_code = 'CONSOLIDATION_DONE'
        category = 'Action'
    elif package.status == 'handling_special_requests':
        logger.info("Sending email alert on customer special requests")
        ctx['pending_special_requests'] = package.pending_special_requests_list()
        communication_type_code = 'SPECIAL_REQUESTS'
        category = 'Info'
    elif package.status == 'handling_special_requests_done':
        logger.info("Sending email alert on customer special requests done for package: %s" % package.upc)
        ctx['fulfilled_special_requests'] = package.fulfilled_special_requests_list()
        ctx['customized_services'] = package.get_customized_services()
        try:
            ctx['customized_services_done'] = package.special_requests.custom_requests_done
        except ObjectDoesNotExist:
            ctx['customized_services_done'] = False
        ctx['customized_services_brief'] = package.get_customized_services_brief()
        communication_type_code = 'SPECIAL_REQUESTS_DONE'
        category = 'Action'
    elif package.status == 'returned_to_sender':
        logger.info("Sending email alert on returned to sender package: %s" % package.upc)
        communication_type_code = 'RETURNED_TO_SENDER'
        category = 'Info'
    elif package.status == 'discarded':
        logger.info("Sending email alert on discarded package: %s" % package.upc)
        communication_type_code = 'DISCARDED_PACKAGE'
        category = 'Info'
    #elif package.status == 'take_measures_done':
    #    logger.info("Sending email alert on take measures done for package: %s" % package.upc)
    #    communication_type_code = 'TAKE_MEASURES_DONE'
    #    category = 'Action'
    else:
        return

    if customer:
        msgs = CommunicationEventType.objects.get_and_render(
                code=communication_type_code, context=ctx)
        dispatcher = Dispatcher()
        dispatcher.dispatch_user_messages(customer, msgs)
        #add site notification
        ctx['no_display'] = True
        msgs = CommunicationEventType.objects.get_and_render(
                code=communication_type_code, context=ctx)
        dispatcher.notify_user(customer, msgs['subject'], msgs['html'], category=category)
    else:
        logger.error("None customer received")


def send_tracker_update_alert(order, tracking_details, carrier, display_carrier, tracking_number, latest_status):
    #reverse tracking details, last is first
    tracking_details.reverse()
    # treat error status as failure
    if latest_status == 'error':
        latest_status = 'failure'
    #send tracking info to customer
    ctx = {
        'order': order,
        'shipping_info': tracking_details,
        'carrier': carrier,
        'display_carrier': display_carrier,
        'tracking_number': tracking_number,
        'latest_status': latest_status
    }

    msgs = CommunicationEventType.objects.get_and_render(
            code='ORDER_TRACKING', context=ctx)
    dispatcher = Dispatcher()
    dispatcher.dispatch_user_messages(order.user, msgs)
    ctx['no_display'] = True
    msgs = CommunicationEventType.objects.get_and_render(
            code='ORDER_TRACKING', context=ctx)
    #add site notification
    dispatcher.notify_user(order.user, msgs['subject'], msgs['html'], category='Info')



def send_fee_alert(fee_type, customer, package, **kwargs):
    if customer:
        ctx = {'package': package}
        ctx.update(kwargs)
        if fee_type == 'missing_client_id':
            logger.info("Sending email alert for missing client id for package: %s" % package)
            msgs = CommunicationEventType.objects.get_and_render(
                    code='MISSING_CLIENT_ID', context=ctx)
            dispatcher = Dispatcher()
            dispatcher.dispatch_user_messages(customer, msgs)
            ctx['no_display'] = True
            msgs = CommunicationEventType.objects.get_and_render(
                    code='MISSING_CLIENT_ID', context=ctx)
            #add site notification
            dispatcher.notify_user(customer, msgs['subject'], msgs['html'], category='Info')
    else:
        logger.error("No customer received")


def send_damaged_package_return_to_store_alert(customer, store_name):
    if customer:
        ctx = {'store_name': store_name}
        logger.info("Sending email alert for damaged package that returned to store")
        msgs = CommunicationEventType.objects.get_and_render(
                code='DAMAGED_PACKAGE', context=ctx)
        dispatcher = Dispatcher()
        dispatcher.dispatch_user_messages(customer, msgs)
        #add site notification
        ctx['no_display'] = True
        msgs = CommunicationEventType.objects.get_and_render(
                    code='DAMAGED_PACKAGE', context=ctx)
        dispatcher.notify_user(customer, msgs['subject'], msgs['html'], category='Info')
    else:
        logger.error("No customer received")


def send_returned_package_alert(customer, package, return_reason):
    if customer:
        ctx = {
            'package': package,
            'return_reason': return_reason
        }
        logger.info("Sending email alert for receiving returned package")
        msgs = CommunicationEventType.objects.get_and_render(
            code='RETURNED_PACKAGE', context=ctx)
        dispatcher = Dispatcher()
        dispatcher.dispatch_user_messages(customer, msgs)
        #add site notification
        ctx['no_display'] = True
        msgs = CommunicationEventType.objects.get_and_render(
                    code='RETURNED_PACKAGE', context=ctx)
        dispatcher.notify_user(customer, msgs['subject'], msgs['html'], category='Info')
    else:
        logger.error("No customer received")


def send_registration_email(user):
    """
    Welcome email needs to be sent only once, therefore we have a validation
    that checks if such email was already sent to the user
    """
    profile = user.get_profile()
    if profile.is_affiliate_account():
        code = 'AFFILIATE_REGISTRATION'
    else:
        code = 'REGISTRATION'

    #this function returns all facilities address, currently we have only 1 facility
    #therefore, we take the first address
    warehouse_address_list = utils.get_warehouse_address()
    private_addresses = profile.generate_virtual_addresses(warehouse_address_list)
    exclusive_club_member = profile.get_exclusive_club() is not None
    ctx = {
        'user': user,
        'exclusive_club_member': exclusive_club_member,
        'private_addresses': private_addresses,
    }
    if not settings.DEBUG:
        ctx['headers'] = {'X-SMTPAPI': json.dumps({"category": "Post Signup"})}
    messages = CommunicationEventType.objects.get_and_render(code, ctx)

    try:
        Email.objects.get(user=user,
                          subject=messages['subject'])
    except Email.DoesNotExist:
        pass
    else:
        return

    if messages and messages['body']:
        Dispatcher().dispatch_user_messages(user, messages)


def add_email_confirmation_notification(user):
    profile = user.get_profile()
    if profile.is_affiliate_account():
        body_html_tpl = loader.get_template(
            'customer/alerts/site_notifications/affiliate_email_confirmation.html')
    else:
        body_html_tpl = loader.get_template(
            'customer/alerts/site_notifications/email_confirmation.html')
    ctx = Context({
        'email': user.email,
        'no_display': True,
    })
    body = body_html_tpl.render(ctx)
    subject = _("Confirm your email address")
    Dispatcher().notify_user(user, subject, body, category='Action')

def add_new_registration_notification(user):
    profile = user.get_profile()
    if profile.is_affiliate_account():
        body_html_tpl = loader.get_template(
            'customer/alerts/site_notifications/affiliate_welcome_message.html')
    else:
        body_html_tpl = loader.get_template(
            'customer/alerts/site_notifications/welcome_message.html')
    ctx = Context({
        'referrals_url': reverse('customer:referrals-index'),
        'no_display': True,
    })
    body = body_html_tpl.render(ctx)
    subject = _("Welcome aboard!")
    Dispatcher().notify_user(user, subject, body, category='Info')
    add_email_confirmation_notification(user)


def get_email_confirmation_url(user, token_generator):
    """
    Generate a password-reset URL for a given user
    """
    return reverse('customer:email-confirmation-confirm', kwargs={
        'uidb36': int_to_base36(user.id),
        'token': token_generator.make_token(user)})

def send_email_confirmation_email(user, proactive=False, profile=None, issuer=None):
    if not profile:
        profile = user.get_profile()
    if profile.is_affiliate_account():
        code = 'AFFILIATE_EMAIL_CONFIRMATION'
    else:
        code = 'EMAIL_CONFIRMATION'
    ctx = {
        'user': user,
        'issuer': issuer,
        'confirmation_url': get_email_confirmation_url(user, tokens.email_confirmation_token_generator),
        'proactive': proactive
    }
    if not settings.DEBUG:
        ctx['headers'] = {'X-SMTPAPI': json.dumps({"category": "Confirm Email Address"})}
    msgs = CommunicationEventType.objects.get_and_render(code, ctx)
    Dispatcher().dispatch_user_messages(user, msgs)


def send_incomplete_customs_declaration_email(order):
    code = 'INCOMPLETE_CUSTOMS_DECLARATION'
    ctx = {
        'order': order,
        'user': order.user
    }
    if not settings.DEBUG:
        ctx['headers'] = {'X-SMTPAPI': json.dumps({"category": "Incomplete Customs Declaration"})}
    msgs = CommunicationEventType.objects.get_and_render(code, ctx)
    Dispatcher().dispatch_user_messages(order.user, msgs)


def send_thirty_minutes_post_signup_email(user):
    email_subject_tpl = loader.get_template('customer/alerts/emails/thirty_minutes_post_signup_subject.txt')
    email_body_tpl = loader.get_template('customer/alerts/emails/thirty_minutes_post_signup_body.txt')
    #email_body_html_tpl = loader.get_template('customer/alerts/emails/thirty_minutes_post_signup_body.html')
    now = datetime.now()
    ctx = Context({'user': user})
    subject = email_subject_tpl.render(ctx).strip()
    body = email_body_tpl.render(ctx)
    #html_body = email_body_html_tpl.render(ctx)
    # Build email and add to list
    email = {
        'recipients': [user.email],
        'sender': 'Leo | USendHome <leo@usendhome.com>',
        'subject': subject,
        'message': body,
        #'html_message': html_body,
        'priority': 'medium',
        'scheduled_time': now + timedelta(minutes=30)
    }
    mail.send(**email)

def send_account_verification_email(user, account_status_pk):
    ctx = {
        'user_name': user.get_full_name(),
        'account_verify_url': reverse('customer:account-verify',
                                    kwargs={'pk': account_status_pk})
    }
    logger.info("Sending email alert for account verification")
    msgs = CommunicationEventType.objects.get_and_render(
        code='ACCOUNT_VERIFICATION', context=ctx)
    dispatcher = Dispatcher()
    dispatcher.dispatch_user_messages(user, msgs)
    #add site notification
    ctx['no_display'] = True
    msgs = CommunicationEventType.objects.get_and_render(
            code='ACCOUNT_VERIFICATION', context=ctx)
    dispatcher.notify_user(user, msgs['subject'], msgs['html'], category='Action')

def send_account_verification_verdict_email(user, is_verified, more_documents, obj):
    ctx = {
        'user_name': user.get_full_name(),
        'is_verified': is_verified,
        'more_documents': more_documents,
        'account_status': obj
    }
    logger.info("Sending email alert for account verification verdict")
    msgs = CommunicationEventType.objects.get_and_render(
        code='ACCOUNT_VERIFICATION_VERDICT', context=ctx)
    dispatcher = Dispatcher()
    dispatcher.dispatch_user_messages(user, msgs)
    #add site notification
    ctx['no_display'] = True
    msgs = CommunicationEventType.objects.get_and_render(
            code='ACCOUNT_VERIFICATION_VERDICT', context=ctx)
    dispatcher.notify_user(user, msgs['subject'], msgs['html'], category='Action')

def send_additional_receiver_verification_verdict_email(user, is_verified, more_documents, obj):
    ctx = {
        'user_name': user.get_full_name(),
        'is_verified': is_verified,
        'additional_receiver_name': obj.get_full_name(),
        'more_documents': more_documents,
        'additional_receiver': obj
    }
    logger.info("Sending email alert for additional receiver verification verdict")
    msgs = CommunicationEventType.objects.get_and_render(
        code='ADDITIONAL_RECEIVER_VERIFICATION_VERDICT', context=ctx)
    dispatcher = Dispatcher()
    dispatcher.dispatch_user_messages(user, msgs)
    #add site notification
    ctx['no_display'] = True
    msgs = CommunicationEventType.objects.get_and_render(
            code='ADDITIONAL_RECEIVER_VERIFICATION_VERDICT', context=ctx)
    dispatcher.notify_user(user, msgs['subject'], msgs['html'], category='Action')

def send_order_confirmation_email(order, **kwargs):
    code = 'ORDER_PLACED'
    ctx = {'user': order.user,
           'order': order,
           'lines': order.lines.all()}

    try:
        event_type = CommunicationEventType.objects.get(code=code)
    except CommunicationEventType.DoesNotExist:
        # No event-type in database, attempt to find templates for this
        # type and render them immediately to get the messages.  Since we
        # have not CommunicationEventType to link to, we can't create a
        # CommunicationEvent instance.
        messages = CommunicationEventType.objects.get_and_render(code, ctx)
        event_type = None
    else:
        # Create CommunicationEvent
        CommunicationEvent._default_manager.create(
            order=order, event_type=event_type)
        messages = event_type.get_messages(ctx)

    if messages and messages['body']:
        logger.info("Order #%s - sending %s messages", order.number, code)
        dispatcher = Dispatcher(logger)
        dispatcher.dispatch_order_messages(order, messages,
                                           event_type, **kwargs)
    else:
        logger.warning("Order #%s - no %s communication event type",
                       order.number, code)


def send_order_cancelled_email(order, cancelled_reason, refund_given, **kwargs):
    ctx = {
        'order_number': order.number,
        'cancelled_reason': cancelled_reason,
        'refund_given': refund_given
    }
    ctx.update(kwargs)
    logger.info("Sending email alert on cancelled order: %s" % order)
    msgs = CommunicationEventType.objects.get_and_render(
        code='CANCELLED_ORDER', context=ctx)
    dispatcher = Dispatcher()
    dispatcher.dispatch_order_messages(order, msgs)
    #add site notification
    ctx['no_display'] = True
    msgs = CommunicationEventType.objects.get_and_render(
            code='CANCELLED_ORDER', context=ctx)
    dispatcher.notify_user(order.user, msgs['subject'], msgs['html'], category='Info')


def get_complete_registration_url(user, token_generator, issuer):
    """
    Generate a complete-registration URL for a given user
    """
    return reverse('customer:api-complete-registration', kwargs={
        'uidb36': int_to_base36(user.id),
        'token': token_generator.make_token(user),
        'issuer': base64.b64encode(issuer)})

def send_api_complete_registration_email(user, issuer):
    code = 'API_COMPLETE_REGISTRATION'
    ctx = {
        'user': user,
        'issuer': issuer,
        'complete_registration_url': get_complete_registration_url(
            user, tokens.api_registration_token_generator, issuer),
    }
    if not settings.DEBUG:
        ctx['headers'] = {'X-SMTPAPI': json.dumps({"category": "API Account Setup 1"})}
    msgs = CommunicationEventType.objects.get_and_render(code, ctx)
    Dispatcher().dispatch_user_messages(user, msgs)

def get_exclusive_club_url(user, token_generator, club):
    """
    Generate a complete-registration URL for a given user
    """
    club_url = reverse('customer:exclusive-club-join', kwargs={
        'uidb36': int_to_base36(user.id),
        'token': token_generator.make_token(user),
        'club': base64.b64encode(club)})
    return  "https://usendhome.com{}".format(club_url)

def send_exclusive_club_email(user, club):
    code = 'EXCLUSIVE_CLUB'
    ctx = {
        'name': user.first_name.title(),
        'club': club,
    }

    if not settings.DEBUG:
        category = "Join {} Exclusive Club #2".format(club)
        ctx['headers'] = {'X-SMTPAPI': json.dumps({"category": category})}

    msgs = CommunicationEventType.objects.get_and_render(code, ctx)
    dispatcher = Dispatcher()
    dispatcher.dispatch_user_messages(user, msgs)
    #add site notification
    ctx['no_display'] = True
    msgs = CommunicationEventType.objects.get_and_render(code=code, context=ctx)
    dispatcher.notify_user(user, msgs['subject'], msgs['html'], category='Action')

def send_thirty_minutes_post_api_registration_email(user, issuer):
    email_subject_tpl = loader.get_template('customer/alerts/emails/complete_signup_process_follow_up_subject.txt')
    email_body_tpl = loader.get_template('customer/alerts/emails/complete_signup_process_follow_up_body.txt')
    email_body_html_tpl = loader.get_template('customer/alerts/emails/complete_signup_process_follow_up_body.html')
    data = app_utils.get_site_properties()
    data.update({
        'user': user,
        'issuer': issuer,
        'complete_registration_url': get_complete_registration_url(
            user, tokens.api_registration_token_generator, issuer)
    })
    ctx = Context(data)
    subject = email_subject_tpl.render(ctx).strip()
    body = email_body_tpl.render(ctx)
    html_body = email_body_html_tpl.render(ctx)
    # Build email and add to list
    email = {
        'recipients': [user.email],
        'sender': 'USendHome <support@usendhome.com>',
        'subject': subject,
        'message': body,
        'html_message': html_body,
    }
    #add category for sendgrid analytics
    if not settings.DEBUG:
        email['headers'] = {'X-SMTPAPI': json.dumps({"category": "API Account Setup 2"})}
    mail.send(**email)
