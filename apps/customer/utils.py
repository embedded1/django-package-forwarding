from oscar.apps.customer.utils import Dispatcher as CoreDispatcher
from django.db.models import get_model
from django.template import Context, loader
from django.conf import settings
from apps import utils
from apps.customer.models import Notification
from .models import Email
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.utils.translation import ugettext as _
from django.core.cache import cache
import os
import zipfile
import logging


logger = logging.getLogger("management_commands")
CommunicationEventType = get_model('customer', 'communicationeventtype')


class Dispatcher(CoreDispatcher):
    def notify_user(self, user, subject, body, category=None):
        """
        Send a simple notification to a user
        """
        Notification.objects.create(
            recipient=user,
            subject=subject,
            body=body,
            category=category)


    def notify_users(self, users, subject, body, category=None):
        """
        Send a simple notification to an iterable of users
        """
        for user in users:
            if user.is_active:
                self.notify_user(user, subject, body, category)

    def send_user_email_messages(self, user, messages):
        """
        Sends message to the registered user / customer
        We don't save emails in DB
        """
        if not user.email:
            self.logger.warning("Unable to send email messages as user #%d has no email address" % user.id)
            return
        if not user.is_active:
            self.logger.warning("We don't send out emails to inactive user: #%d" % user.id)
            return

        email = self.send_email_messages(user.email, messages)
        # Is user is signed in, record the event for audit
        if email and user.is_authenticated():
            Email._default_manager.create(user=user,
                                          subject=email.subject,
                                          body_text=email.body,
                                          body_html=messages['html'])

    def send_email_messages(self, recipient, messages):
        """
        Plain email sending to the specified recipient
        """
        if hasattr(settings, 'OSCAR_FROM_EMAIL'):
            from_email = settings.OSCAR_FROM_EMAIL
        else:
            from_email = None

        # Determine whether we are sending a HTML version too
        if messages['html']:
            email = EmailMultiAlternatives(messages['subject'],
                                           messages['body'],
                                           from_email=from_email,
                                           to=[recipient],
                                           headers=messages['headers'])
            email.attach_alternative(messages['html'], "text/html")
        else:
            email = EmailMessage(messages['subject'],
                                 messages['body'],
                                 from_email=from_email,
                                 to=[recipient],
                                 headers=messages['headers'])
        self.logger.info("Sending email to %s" % recipient)
        email.send()

        return email



def create_zip_archive(files_to_zip, zip_full_path):
    #create directory if not already exists
    zip_directory = os.path.dirname(zip_full_path)
    if not os.path.exists(zip_directory):
        os.makedirs(zip_directory)

    # The zip compressor
    zf = zipfile.ZipFile(zip_full_path, "w")

    for file in files_to_zip:
        _, fname = os.path.split(file)
        zf.write(file, fname)

    # Must close zip for all contents to be written
    zf.close()


class RegisterSessionData(object):
    SESSION_KEY = 'register_data'

    def __init__(self, request):
        self.request = request
        if self.SESSION_KEY not in self.request.session:
            self.request.session[self.SESSION_KEY] = {}

    def store_account_data(self, data):
        self.request.session[self.SESSION_KEY] = data
        self.request.session.modified = True
        #save data also in cache for fallback
        cache.set(self.request.session.session_key, data, timeout=60 * 60 * 24 * 3) #3 days

    def get_account_data(self):
        account_data = self.request.session.get(self.SESSION_KEY)
        if not account_data:
            #check in cache
            retries = 0
            while not account_data and retries < 3:
                account_data = cache.get(self.request.session.session_key, {})
                retries += 1
        return account_data

    def delete_account_data(self):
        cache.delete(self.request.session.session_key)
        self.request.session[self.SESSION_KEY] = {}


def add_user_signed_up_site_notification(referrer, referee):
    # Load templates
    dispatcher = Dispatcher()
    referee_name = referee.get_full_name().title()
    body_html_tpl = loader.get_template('customer/alerts/site_notifications/referrer_user_signup_reward_message.html')
    data = {
        'referee_name': referee_name,
        'no_display': True
    }
    data.update(utils.get_site_properties())
    ctx = Context(data)
    #first add referrer site notification
    subject =  _("%s has just signed up using your referral link" % referee_name)
    html_body = body_html_tpl.render(ctx)
    dispatcher.notify_user(referrer, subject, html_body, category="Action")
    #then, add referee site notification
    subject =  _("Shipping Credit Available" )
    body_html_tpl = loader.get_template('customer/alerts/site_notifications/referee_user_signup_reward_message.html')
    html_body = body_html_tpl.render(ctx)
    dispatcher.notify_user(referee, subject, html_body, category="Action")


def get_mailchimp_group_id(user, list_id, profile=None):
    if not profile:
        profile = user.get_profile()

    mailchimp_list_groups = settings.MAILCHIMP_LIST_GROUPS[list_id]

    if not profile.email_confirmed:
        group_id = mailchimp_list_groups[settings.MAILCHIMP_GROUP_UNCONFIRMED]
    else:
        is_customer = user.orders\
                      .exclude(status__in=['Pending', 'Cancelled', 'Refunded']).exists()
        if is_customer:
            group_id = mailchimp_list_groups[settings.MAILCHIMP_GROUP_CUSTOMERS]
        else:
            group_id = mailchimp_list_groups[settings.MAILCHIMP_GROUP_CONFIRMED]
    return group_id

