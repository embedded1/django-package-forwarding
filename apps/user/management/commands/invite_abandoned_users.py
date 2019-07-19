from django.utils.translation import ugettext as _
from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from django.template import Context, loader
from apps.user.models import PotentialUser
from datetime import datetime, timedelta
from post_office import mail
from apps import utils
import logging


logger = logging.getLogger("management_commands")

class Command(BaseCommand):
    """
    Check for packages with 3 days before storage fee applied and alert the user
    have registered for an alert.
    """
    help = _("Send notification to all potential users that visited the site yesterday")

    def handle(self, verbosity, **options):
        """
        Send warehouse migration email to all customers (non staff and partner related users)
        """
        now = datetime.now()
        now = now.replace(hour=0, minute=0, second=0, microsecond=0)
        #get only year month and day
        start_range = now - timedelta(days=1)
        end_range = now
        potential_users = PotentialUser.objects\
            .filter(user__isnull=True,
                    date_visited__range=(start_range, end_range))

        # Load templates
        email_subject_tpl = loader.get_template('customer/alerts/emails/abandoned_signup_subject.txt')
        email_body_tpl = loader.get_template('customer/alerts/emails/abandoned_signup_body.txt')
        email_body_html_tpl = loader.get_template('customer/alerts/emails/abandoned_signup_body.html')

        emails = []
        data = utils.get_site_properties()
        ctx = Context(data)
        for user in potential_users:
            subject =  email_subject_tpl.render(ctx).strip()
            body = email_body_tpl.render(ctx)
            html_body = email_body_html_tpl.render(ctx)

            # Build email and add to list
            email = {
                'recipients': [user.email],
                'sender': 'Leo | USendHome <leo@usendhome.com>',
                'subject': subject,
                'message': body,
                'html_message': html_body
            }

            emails.append(email)

        #we use celery to dispatch emails, therefore we iterate over all emails and add
        #each one of them to the task queue,send_many doesn't work with priority = now
        #therefore, we use the regular send mail
        for email in emails:
            try:
                mail.send(**email)
            except ValidationError, e:
                logger.critical('send_storage_alerts post_office send validation error: %s, email = %s'
                                % (str(e), email['recipients'][0]))


