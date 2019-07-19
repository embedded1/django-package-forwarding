from django.utils.translation import ugettext as _
from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from django.template import Context, loader
from django.db.models import get_model
from oscar.core.loading import get_class
from post_office import mail
from apps import utils
import logging

User = get_model('auth', 'User')
Dispatcher = get_class('customer.utils', 'Dispatcher')
logger = logging.getLogger("management_commands")

class Command(BaseCommand):
    """
    Check for packages with 3 days before storage fee applied and alert the user
    have registered for an alert.
    """
    help = _("Send email notification to users who downloaded the chrome extension for rating ")

    def handle(self, **options):
        """
        Check all packages that have 3 days left to free storage and alert the customer
        Regular packages have 10 free days and consolidated packages have 30 free days
        therefore we separate both cases
        There's another interesting case which is packages that wait for consolidation - we can pick
        the oldest package in warehouse amount them and count it as consolidated package - the email notification
        will be changed though
        """
        emails = []
        now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = now - timedelta(days=7)
        end_date = start_date + timedelta(hours=23, minutes=59, seconds=59)
        chrome_extension_added_7_days_ago = User\
            .objects\
            .filter(profile__added_chrome_extension=True,
                    profile__date_chrome_extension_added__range=(start_date, end_date))
        # Load templates
        email_subject_tpl = loader.get_template('customer/alerts/emails/chrome_extension_rating_subject.txt')
        email_body_tpl = loader.get_template('customer/alerts/emails/chrome_extension_rating_body.txt')
        email_body_html_tpl = loader.get_template('customer/alerts/emails/chrome_extension_rating_body.html')
        for user in chrome_extension_added_7_days_ago:
            data = {'full_name': user.get_full_name().title()}
            data.update(utils.get_site_properties())
            ctx = Context(data)
            subject =  email_subject_tpl.render(ctx).strip()
            body = email_body_tpl.render(ctx)
            html_body = email_body_html_tpl.render(ctx)

            # Build email and add to list
            email = {
                'recipients': [user.email],
                'sender': 'Leo Jones <leo@usendhome.com>',
                'subject': subject,
                'message': body,
                'html_message': html_body
            }
            emails.append(email)

            #add site notification
            data['no_display'] = True
            ctx = Context(data)
            html_body = email_body_html_tpl.render(ctx)
            Dispatcher().notify_user(user, subject, html_body, category="Action")

        #we use celery to dispatch emails, therefore we iterate over all emails and add
        #each one of them to the task queue,send_many doesn't work with priority = now
        #therefore, we use the regular send mail
        for email in emails:
            try:
                mail.send(**email)
            except ValidationError, e:
                logger.critical('send_storage_alerts post_office send validation error: %s, email = %s'
                                % (str(e), email['recipients'][0]))



