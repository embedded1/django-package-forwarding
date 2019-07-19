from django.dispatch import receiver
from apps.catalogue.signals import product_status_change_alert
from oscar.apps.customer.signals import user_registered
from django.core.urlresolvers import reverse
from pinax.referrals.middleware import SessionJumpingMiddleware
from datetime import datetime
from apps.rewards import responses
from django.conf import settings
from .. import utils
from ..signals import affiliate_registered
import logging


logger = logging.getLogger("management_commands")

@receiver(product_status_change_alert)
def send_product_status_change_alert(sender, customer, package, extra_msg, **kwargs):
    """
    send alerts to customer based on package status
    """
    from apps.customer.alerts.senders import send_product_change_status_alert
    send_product_change_status_alert(customer, package, extra_msg)


@receiver(user_registered)
def user_registered_handler(sender, user, request, **kwargs):
    """
    Send alert to admins on new registered customer
    and send  registration email
    """
    from apps.customer.alerts import senders
    from apps.user import alerts
    from apps.user.models import GoogleAnalyticsData
    from pinax.referrals.models import Referral
    from apps.customer.tasks import mixpanel_post_registration, subscribe_user
    import urllib
    #prevent sending when user is superuser
    if not user.is_superuser:
        alerts.send_new_user_alert(user)
        #Create user's referral code and link to profile
        referral = Referral.create(
            redirect_to=reverse('promotions:home'),
            user=user)
        profile = kwargs.get('profile')
        if not profile:
            profile = user.get_profile()
        profile.referral = referral
        profile.added_chrome_extension = request.session.get('added_chrome_extension', False)
        if profile.added_chrome_extension:
            profile.date_chrome_extension_added = datetime.now()

        if not kwargs.get('post_signup_emails_sent'):
            if profile.email_confirmed:
                senders.send_registration_email(user)
            else:
                # we send the confirm email address email upon API registration
                # therefore, no need to resend it here
                if not profile.signed_up_through_api():
                    senders.send_email_confirmation_email(user)
            senders.send_thirty_minutes_post_signup_email(user)

        #give credit for newly signed up user if he followed a referral link
        #sender can be one of those two:
        # 1 - RegisterProfileView
        # 2 - python_social_auth django strategy
        #both have a request property so we're all covered
        # normally anafero middleware would handle this, but
        # because django-registration calls `login()`, the session_key
        # changes and `Referral.record_response()` won't work since the middleware hasn't
        # performed this cleanup
        if not request.user.is_authenticated():
            request.user = user
        anafero_middleware = SessionJumpingMiddleware()
        anafero_middleware.process_request(request)
        response = responses.credit_signup(request)
        if response:
            #add site notification to let the referrer know that a user
            #has just registered following his referral link
            utils.add_user_signed_up_site_notification(
                response.referral.user,
                response.user)

        #save external referer
        external_referer = request.session.get('external_referer')
        if external_referer is not None:
            profile.external_referer = external_referer

        #need to identify the new user in mixpanel - we're doing this in the background
        #as we must call a blocking function
        mixpanel_anon_id = kwargs.get('mixpanel_anon_id')
        backend = kwargs.get('backend', 'Email')
        data = {
            'mixpanel_anon_id': mixpanel_anon_id,
            'user': user,
            'profile': profile,
            'backend': backend,
            'referrer_mailbox': None,
        }

        #get registration type
        register_type = kwargs.get('register_type')

        #check for referral data
        referrer = response.referral.user if response else None
        if referrer:
            register_type = 'invite'
            data['referrer_mailbox'] = referrer.get_profile().uuid
            data['referrer_name'] = referrer.get_full_name()

        #check for analytics data
        if 'adwords_data' in request.session:
            term = request.session['adwords_data'].get('utm_term')
            content = request.session['adwords_data'].get('utm_content')
            gad_kwargs = {
                'source': request.session['adwords_data'].get('utm_source'),
                'medium': request.session['adwords_data'].get('utm_medium'),
                'name': request.session['adwords_data'].get('utm_campaign'),
                'term': urllib.unquote(term) if term else None,
                'content': urllib.unquote(content) if content else None,
                'profile': profile
            }
            try:
                GoogleAnalyticsData.objects.create(**gad_kwargs)
            except:
                logger.exception("Error creating GoogleAnalyticsData object")

            if gad_kwargs['medium'] and gad_kwargs['medium'].lower() == 'cpc':
                register_type = 'paid'

        data['register_type'] = register_type
        mixpanel_post_registration.apply_async(
            kwargs=data,
            queue='analytics'
        )

        if not profile.email_confirmed:
            #move newly registered user to the unconfirmed group if email is not confirmed
            #registered users via API can have their email address confirmed at this stage
            list_id = settings.MAILCHIMP_LISTS[settings.MAILCHIMP_LIST_USERS]
            group_id = settings.MAILCHIMP_LIST_GROUPS[list_id][settings.MAILCHIMP_GROUP_UNCONFIRMED]
            subscribe_user.apply_async(
                kwargs={
                    'user': user,
                    'list_id': list_id,
                    'group_settings': {group_id: True},
                    'is_conf_url_required': True
                },
                queue='analytics')

        #save registration info
        if register_type:
            profile.registration_type = register_type
        profile.registration_method = backend
        profile.save()


@receiver(affiliate_registered)
def affiliate_registered_handler(sender, user, **kwargs):
    """
    Send alert to admins on new registered affiliate
    and send registration email
    """
    from . import senders
    from apps.user import alerts
    from apps.customer.tasks import mixpanel_post_registration, subscribe_user
    #prevent sending when user is superuser
    if not user.is_superuser:
        profile = kwargs.get('profile')
        if not profile:
            profile = user.get_profile()
        data = {
            'mixpanel_anon_id': kwargs.get('mixpanel_anon_id'),
            'user': user,
            'profile': profile,
            'backend': 'email',
            'referrer_mailbox': None,
            'register_type': 'affiliate'
        }
        mixpanel_post_registration.apply_async(
            kwargs=data,
            queue='analytics'
        )

        #move newly registered affiliate user to the affiliate unconfirmed group
        list_id = settings.MAILCHIMP_LISTS[settings.MAILCHIMP_LIST_AFFILIATORS]
        group_id = settings.MAILCHIMP_LIST_GROUPS[list_id][settings.MAILCHIMP_GROUP_UNCONFIRMED]
        subscribe_user.apply_async(
            kwargs={
                'user': user,
                'list_id': list_id,
                'group_settings': {group_id: True},
                'is_conf_url_required': True
            },
            queue='analytics')

        alerts.send_new_user_alert(user)
        #senders.send_registration_email(user)
        senders.send_email_confirmation_email(user)
