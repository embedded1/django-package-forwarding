from django.http import HttpResponse
from django.template.loader import render_to_string
from django.template import RequestContext
from django.utils import simplejson as json
from django.contrib.auth import authenticate, login as auth_login
from oscar.apps.customer.mixins import RegisterUserMixin as CoreRegisterUserMixin
from oscar.core.compat import get_user_model
from ipware.ip import get_real_ip
from apps.catalogue.signals import product_status_change_alert
from apps.catalogue.models import Product
from apps.order.models import Order
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from apps.user.tasks import abandoned_signup_email
from .customs_duties import CUSTOMS_DUTIES_DATA
from django.utils.translation import ugettext as _
from django.template import loader, Context
from django.db.models import get_model
from post_office import mail
from apps import utils
import pygeoip
import os
import logging

logger = logging.getLogger(__name__)
PotentialUser = get_model('user', 'PotentialUser')
User = get_user_model()

class AjaxTemplateMixin(object):
    def dispatch(self, request, *args, **kwargs):
        if not hasattr(self, 'ajax_template_name'):
            split = self.template_name.split('.html')
            split[-1] = '_inner'
            split.append('.html')
            self.ajax_template_name = ''.join(split)
        if request.is_ajax():
            self.template_name = self.ajax_template_name
        return super(AjaxTemplateMixin, self).dispatch(request, *args, **kwargs)

    def json_response(self, ctx=None, flash_messages=None, **kwargs):
        payload = {'messages': flash_messages.to_json() if flash_messages else None}
        payload.update(kwargs)
        if ctx:
            content_html = render_to_string(
                self.template_name,
                RequestContext(self.request, ctx))
            payload['content_html'] = content_html
        return HttpResponse(json.dumps(payload),
                            mimetype="application/json")

class PendingPackagesMixin(object):
    def get_packages(self, user):
        return Product.objects.filter(
            owner=user,
            status__in=self.FILTER_STATUSES,
            product_class__name='package'
        ).order_by('date_created')

    def send_product_status_change_alert(self, package):
        product_status_change_alert.send(
            sender=Product,
            customer=package.owner,
            package=package,
            extra_msg=None
        )

    def get_customs_info(self):
        profile = self.request.user.get_profile()
        customs_info = None
        if profile.country and profile.country in CUSTOMS_DUTIES_DATA:
            customs_info = CUSTOMS_DUTIES_DATA[profile.country]
        return customs_info


    def get_context_data(self, **kwargs):
        ctx = super(PendingPackagesMixin, self).get_context_data(**kwargs)
        ctx['show_first_package_modal'] = self.is_show_first_package_modal(self.request.user)
        customs_info = self.get_customs_info()
        if customs_info:
            ctx['customs_info'] = customs_info
        return ctx

    def is_show_first_package_modal(self, user):
        profile = user.get_profile()
        res = not profile.is_control_panel_modal_shown and \
               not Order.objects.filter(user=user).exists()
        profile.is_control_panel_modal_shown = True
        profile.save()
        return res

class RegisterUserMixin(CoreRegisterUserMixin):
    def add_tour_message(self):
        """
        This function shows a messages to newly registered users with
        a button to start the control panel tour
        we show this welcome tour only for non mobile devices
        for mobile we only show a welcome greeting
        """
        #user_agent = self.request.META.get('HTTP_USER_AGENT', 'mobi')
        #if not re.search('mobi', user_agent, re.IGNORECASE):
        messages.info(
            self.request,
            _("<h4><strong>Welcome aboard!</strong></h4>"
              "<p>Your account has been set up successfully and you can start using your personal US address now.</p>"
              "<p>Take a moment to get familiar with the up-to-date shipping regulations and don't forget to</p>"
              "<p>check out the quick welcome video to get you started easily.</p>"
              "<div class='modal-btns' style='margin-top:10px;'><button id='welcome-msg' class='btn btn-primary' type='button' data-toggle='modal'"
              " data-target='#onboardingModal'><i class='fa fa-play-circle'></i>"
              " Watch Video</button>"
              "<button id='shipping-regs' class='btn btn-primary' type='button'><i class='fa fa-globe'></i>"
              " Read Regulations</button></div>"),
            extra_tags='safe noicon'
        )
        #else:
        #    messages.info(
        #        self.request,
        #        _("<h4><strong>Welcome aboard!</strong></h4>"
        #          "<p>Your private USendHome shipping address has been set up successfully.</p>"
        #          "<p>You may start using it right away.</p>"),
        #        extra_tags='safe noicon'
        #    )


    def register_user(self, user_data):
        """
        Modified oscar's function to suit our needs, we send an email confirmation message to newly
        registered users and it relies on the last_login attribute.
        Therefore, we must first login and then send the user_registered signal that triggers this
        confirmation message
        """
        plain_password = user_data.pop('password', '')
        email = user_data.pop('email', '')
        user_data['password'] = make_password(plain_password)
        user, created = User.objects.get_or_create(email=email, defaults=user_data)
        #update attributes in case user already exists
        if not created:
            user.password = user_data['password']
            user.first_name = user_data.get('first_name', user.first_name)
            user.last_name = user_data.get('last_name', user.last_name)
            user.save()
        # We have to authenticate before login
        try:
            user = authenticate(
                username=user.email,
                password=plain_password)
        except User.MultipleObjectsReturned:
            # Handle race condition where the registration request is made
            # multiple times in quick succession.  This leads to both requests
            # passing the uniqueness check and creating users (as the first one
            # hasn't committed when the second one runs the check).  We retain
            # the first one and delete the dupes.
            users = User.objects.filter(email=user.email)
            user = users[0]
            for u in users[1:]:
                u.delete()

        auth_login(self.request, user)
        return user

    def get_user_extra_data(self, request):
        if settings.DEBUG:
            return {
                'city': 'Tel Aviv',
                'country': 'ISR',
                'ip': '79.177.54.60'
            }
        ip = get_real_ip(request)
        if ip is not None:
           # we have a real, public ip address for user
            try:
                db_file = os.path.join(settings.PROJECT_DIR, 'static', 'maxmind', 'GeoLiteCity.dat')
            except IOError:
                logger.critical('Maxmind DB file not found')
            else:
                gi = pygeoip.GeoIP(db_file)
                record = gi.record_by_addr(ip)
                if record is not None:
                    try:
                        return {
                            'city': record['city'] or record['metro_code'],
                            'country': record['country_code3'],
                            'ip': ip
                        }
                    except KeyError:
                        logger.error('Maxmind record key not found')
        return None

    def align_photos_service(self):
        one_photo_selected = self.post_data.get('is_one_photo', 'off') == 'on'
        three_photo_selected = self.post_data.get('is_three_photos', 'off') == 'on'
        if three_photo_selected:
            self.post_data['is_photos'] = 'Three'
        elif one_photo_selected:
            self.post_data['is_photos'] = 'One'
        else:
            self.post_data['is_photos'] = 'Zero'

    def link_potential_user(self, user):
        PotentialUser.objects\
            .filter(email=user.email.lower())\
            .update(user=user)

    def capture_potential_user_email(self, email):
        if email:
            _, ___ = PotentialUser.objects.\
                get_or_create(email=email.lower())
            #ask celery to send an email in 30 minutes in
            #case the user didn't register by then
            abandoned_signup_email.apply_async(
                kwargs={'email': email},
                queue='analytics',
                countdown=30 * 60) #wait 30 min

class AuthenticationDocumentsNotificationMixin(object):
    def send_admin_notification_email(self, unit, subject):
            """
            Sends the message to admins when authentication documents were uploaded.
            """
            from_email = settings.DEFAULT_FROM_EMAIL
            email_recipients = [settings.ADMINS[0][1]]
            ctx = {'unit': unit}
            ctx.update(utils.get_site_properties())
            ctx = Context(ctx)
            body_tpl = loader.get_template("customer/emails/verification/verification_body.txt")
            html_body_tpl = loader.get_template("customer/emails/verification/verification_body.html")

            mail.send(
                recipients=email_recipients,
                sender=from_email,
                subject=subject,
                message=body_tpl.render(ctx),
                html_message=html_body_tpl.render(ctx),
                priority='now')


