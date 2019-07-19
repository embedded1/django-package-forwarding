from django.utils.translation import ugettext as _
from django.core.management.base import BaseCommand
from django.template import loader, Context
from django.core import mail
from django.conf import settings
from django.contrib.auth.models import User
from decimal import Decimal as D
import requests
import logging


logger = logging.getLogger("management_commands")

class Command(BaseCommand):
    """
    Background task that periodaclly checks if registered user is using a proxy service
    """
    help = _("Proxy detection")

    def calc_proxy_score(self, ip):
        payload = {
            'l': settings.MINFRAUD_LICENSE_KEY,
            'i': ip
        }
        response = requests.get('https://minfraud.maxmind.com/app/ipauth_http', params=payload)

        if response.status_code != requests.codes.ok:
            logger.error("Request failed with status %s" % response.status_code)
            return None

        proxy = dict( f.split('=') for f in response.text.split(';') )

        if 'err' in proxy and len(proxy['err']):
            logger.error("MaxMind returned an error code for the request: %s" % proxy['err'])
            return None

        return proxy['proxyScore']

    def handle(self, **options):
        users = User.objects.select_related('profile').exclude(
            is_superuser=True).filter(
            is_active=True, profile__ip__isnull=False, profile__proxy_score__isnull=True)

        emails = []
        for user in users:
            profile = user.get_profile()
            ip = profile.ip
            #call maxmind api to calculate proxy score
            proxy_score = self.calc_proxy_score(ip)
            #save proxy score
            if proxy_score:
                profile.proxy_score = proxy_score
                profile.save()

                #send alert only if we detected a proxy
                if D(proxy_score) != D('0.00'):
                    ctx = Context({
                        'user_name': user.get_full_name(),
                        'proxy_score': proxy_score
                    })

                    subject_tpl = loader.get_template('user/alerts/emails/admins/proxy_detection_subject.txt')
                    body_tpl = loader.get_template('user/alerts/emails/admins/proxy_detection_body.txt')
                    body_html_tpl = loader.get_template('user/alerts/emails/admins/proxy_detection_body.html')

                    # Build email and add to list
                    email = {
                        'subject': subject_tpl.render(ctx).strip(),
                        'message': body_tpl.render(ctx),
                        'html_message': body_html_tpl.render(ctx)
                    }
                    emails.append(email)

        #we use celery to dispatch emails, therefore we iterate over all emails and add
        #each one of them to the task queue,send_many doesn't work with priority = now
        #therefore, we use the regular send mail
        #for email in emails:
        #    mail.mail_admins(**email)




