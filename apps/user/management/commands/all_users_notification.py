from django.utils.translation import ugettext as _
from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from django.template import Context, loader
from django.db.models import get_model
from oscar.core.loading import get_class
from post_office import mail
from django.conf import settings
from django.db.models import Q
from optparse import make_option
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
    help = _("Send notification to all active customers")
    option_list = BaseCommand.option_list + (
        make_option('-t', '--template_base_name', type='string',
            help="Enter template base name without the suffix"),
        make_option('-n', '--only_site_notification', type='string', default='no',
            help="Enter 'yes' for only site notification, no email will be sent, otherwise enter 'no'"),
    )

    def handle(self, verbosity, template_base_name, only_site_notification, **options):
        """
        Send warehouse migration email to all customers (non staff and partner related users)
        """

        #Get all users, excluding staff, partner related users or inactive users
        if not settings.DEBUG:
            customers = User.objects.exclude(
                Q(is_staff=True) |
                Q(partners__isnull=False) |
                Q(is_active=False) |
                Q(profile__email_confirmed=False) |
                Q(email__in=['yanivkoter@gmail.com']))
        else:
            customers = User.objects.filter(email='asili22@gmail.com')

        # Load templates
        template_base = 'customer/alerts/emails/%(base)s' % {'base': template_base_name}
        email_subject_tpl = loader.get_template(template_base+'_subject.txt')
        email_body_tpl = loader.get_template(template_base+'_body.txt')
        email_body_html_tpl = loader.get_template(template_base+'_body.html')

        emails = []
        data = utils.get_site_properties()
        for customer in customers:
            data['customer'] = customer
            ctx = Context(data)
            subject =  email_subject_tpl.render(ctx).strip()
            body = email_body_tpl.render(ctx)
            html_body = email_body_html_tpl.render(ctx)

            # Build email and add to list
            email = {
                'recipients': [customer.email],
                'sender': 'USendHome <support@usendhome.com>',
                'subject': subject,
                'message': body,
                'html_message': html_body
            }

            #add site notification
            data['no_display'] = True
            ctx = Context(data)
            html_body = email_body_html_tpl.render(ctx)
            Dispatcher().notify_user(customer, subject, html_body, category="Info")
            if only_site_notification == 'yes':
                continue
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


