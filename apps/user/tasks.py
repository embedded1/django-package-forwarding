from __future__ import absolute_import
from packageshop.celery import app
from apps.user.models import PotentialUser
from django.core.exceptions import ValidationError
from django.template import Context, loader
from django.utils import simplejson as json
from post_office import mail
from apps import utils
from django.conf import settings
import logging

logger = logging.getLogger("management_commands")


@app.task(ignore_result=True)
def abandoned_signup_email(email, **kwargs):
        try:
            PotentialUser.objects\
                .get(user__isnull=True, email=email)
        except PotentialUser.DoesNotExist:
            return

        # Load templates
        email_subject_tpl = loader.get_template('customer/alerts/emails/abandoned_signup_subject.txt')
        email_body_tpl = loader.get_template('customer/alerts/emails/abandoned_signup_body.txt')
        email_body_html_tpl = loader.get_template('customer/alerts/emails/abandoned_signup_body.html')

        data = utils.get_site_properties()
        ctx = Context(data)

        subject =  email_subject_tpl.render(ctx).strip()
        body = email_body_tpl.render(ctx)
        html_body = email_body_html_tpl.render(ctx)

        # Build email and add to list
        email_data = {
            'recipients': [email],
            'sender': 'Leo | USendHome <leo@usendhome.com>',
            'subject': subject,
            'message': body,
            'html_message': html_body
        }

        #add category for sendgrid analytics
        if not settings.DEBUG:
            email_data['headers'] = {'X-SMTPAPI': json.dumps({"category": "Abandoned Signup"})}

        try:
            mail.send(**email_data)
        except ValidationError, e:
            logger.critical('send_storage_alerts post_office send validation error: %s, email = %s'
                            % (str(e), email_data['recipients'][0]))
