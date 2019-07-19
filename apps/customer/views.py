from apps.customer.alerts import senders
from apps.user import tokens, utils as user_utils
from oscar.apps.customer.views import EmailHistoryView as CoreEmailHistoryView, EmailDetailView as CoreEmailDetailView,\
    AccountAuthView as CoreAccountAuthView, AccountRegistrationView as CoreAccountRegistrationView,\
    ProfileUpdateView as CoreProfileUpdateView, AddressCreateView as\
    CoreAddressCreateView, AddressUpdateView as CoreAddressUpdateView, AddressChangeStatusView as\
    CoreAddressChangeStatusView, AddressListView as CoreAddressListView, AddressDeleteView as CoreAddressDeleteView,\
    OrderHistoryView as CoreOrderHistoryView, ChangePasswordView as CoreChangePasswordView,\
    OrderDetailView as CoreOrderDetailView, LogoutView as CoreLogoutView
from apps.catalogue.models import (
    Product, ProductConsolidationRequests,
    ProductSpecialRequests, AdditionalPackageReceiver,
    PackageReceiverDocument)
from apps.user.models import (
    AccountStatus,
    AccountAuthenticationDocument)
from .mixins import (
    AjaxTemplateMixin, PendingPackagesMixin,
    AuthenticationDocumentsNotificationMixin)
from apps.catalogue.forms import SpecialRequestsForm
from apps.catalogue.cache import ProductCache
from apps.catalogue import utils as catalogue_utils
from oscar.apps.customer.utils import get_password_reset_url
from .forms import (
    ProfileWithEmailForm, ShippingInsuranceClaimForm,
    ProfileWithEmailAndPasswordForm, SettingsForm,
    PackageTrackingForm, ProfileForm, CustomerFeedbackForm,
    AffiliateCreationForm)
from django.http import HttpResponseRedirect
from apps.utils import operation_shut_down
from django.views.generic import (ListView, CreateView, DeleteView)
from django.core.urlresolvers import reverse, reverse_lazy
from django.contrib import messages
from django.views.generic import FormView, RedirectView, TemplateView, DetailView, View
from oscar.core.loading import get_profile_class
from django.utils.translation import ugettext as _
from django.db.models import get_model
from honeypot.decorators import check_honeypot
from decimal import Decimal as D
from apps.dashboard.catalogue.forms import ConsolidationRequestForm
from oscar.apps.customer.mixins import PageTitleMixin
from django.shortcuts import get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from apps.partner.utils import create_package_stock_record
from oscar.core.loading import get_class
from oscar.core.compat import get_user_model
from apps.customer.forms import generate_username
from .forms import (
    AdditionalPackageReceiverForm,
    AdditionalPackageReceiverDocumentFormSet,
    AccountAuthenticationDocumentFormSet)
from django.utils.http import base36_to_int
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import Http404, HttpResponse, HttpResponseNotFound
from oscar.core import ajax
from django.utils import simplejson as json
from post_office import mail
from django.template import loader, Context
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from .utils import RegisterSessionData, create_zip_archive, get_mailchimp_group_id
from django.template.loader import render_to_string
from pinax.referrals.models import Referral
from django.template import RequestContext
from django.contrib.auth import logout
from apps.utils import operation_suspended
import time
import os
import logging
from apps.rewards import responses
from apps.user.uuid import generate_uuid
from oscar.apps.customer.signals import user_registered
from .signals import affiliate_registered
from .tasks import (
    mixpanel_track_email_confirmation,
    mixpanel_track_create_shipping_address,
    mixpanel_track_academy_extra_service_order,
    subscribe_user)
from xhtml2pdf import pisa
from xhtml2pdf.pdf import pisaPDF
from StringIO import StringIO
from pinax.referrals.models import ReferralResponse
from datetime import datetime, timedelta
import copy
import base64




logger = logging.getLogger("management_commands")
ProductClass = get_model('catalogue', 'ProductClass')
User = get_user_model()
CommunicationEventType = get_model('customer', 'communicationeventtype')
Dispatcher = get_class('customer.utils', 'Dispatcher')
RegisterUserMixin = get_class('customer.mixins', 'RegisterUserMixin')
UserAddress = get_model('address', 'UserAddress')
AffiliatorAddress = get_model('address', 'AffiliatorAddress')
Notification = get_model('customer', 'Notification')
Order = get_model('order', 'Order')
Profile = get_model('user', 'Profile')
Country = get_model('address', 'Country')

@check_honeypot(field_name='gender')
def check_honeypot(request):
    pass

class PackageTrackingView(AjaxTemplateMixin, FormView):
    form_class = PackageTrackingForm
    ajax_template_name = "customer/profile/package_tracking_inner.html"

    def get_context_data(self, **kwargs):
        ctx = super(PackageTrackingView, self).get_context_data(**kwargs)
        ctx['package_tracking'] = self.get_shipment_tracking_field()
        return ctx

    def get_shipment_tracking_field(self):
        profile = self.request.user.get_profile()
        return profile.package_tracking

    def get_form_kwargs(self):
        kwargs = super(PackageTrackingView, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse('customer:profile-view')

    def form_valid(self, form):
        if self.request.is_ajax():
            profile = form.save()
            if profile.package_tracking:
                messages.success(self.request, _("All set, we will send you new shipping information as it comes in."))
            else:
                messages.success(self.request, _("Package Tracking disabled."))
            return self.json_response(
                is_valid=True,
                redirect_url=self.get_success_url()
            )
        return HttpResponseRedirect(reverse('customer:profile-view'))

    def form_invalid(self, form):
        if self.request.is_ajax():
            ctx = {'form': form}
            return self.json_response(ctx=ctx)
        return HttpResponseRedirect(reverse('customer:profile-view'))


class ChangePasswordView(AjaxTemplateMixin, CoreChangePasswordView):
    def form_valid(self, form):
        if self.request.is_ajax():
            super(ChangePasswordView, self).form_valid(form)
            return self.json_response(
                is_valid=True,
                redirect_url=self.get_success_url()
            )
        return HttpResponseRedirect(reverse('customer:profile-view'))

    def form_invalid(self, form):
        if self.request.is_ajax():
            ctx = {'form': form}
            return self.json_response(ctx=ctx)
        return HttpResponseRedirect(reverse('customer:profile-view'))


class SettingsUpdateView(AjaxTemplateMixin, CoreProfileUpdateView):
    form_class = SettingsForm
    page_title = _('Change Settings')

    def get_form_kwargs(self):
        kwargs = super(CoreProfileUpdateView, self).get_form_kwargs()
        kwargs['instance'] = self.request.user
        return kwargs

    def form_valid(self, form):
        """
        This is the exact oscar's function, we added 2 functions:
        1 - changed profile to settings
        2 - set email_confirmed to False on email change
        """
        if self.request.is_ajax():
            # Grab current user instance before we save form.  We may need this to
            # send a warning email if the email address is changed.
            messages.success(self.request, _("Settings updated."))
            try:
                old_user = User.objects.get(id=self.request.user.id)
            except User.DoesNotExist:
                old_user = None
            new_user = form.save()
            # We have to look up the email address from the form's
            # cleaned data because the object created by form.save() can
            # either be a user or profile depending on AUTH_PROFILE_MODULE
            new_email = form.cleaned_data['email']
            if old_user and new_email != old_user.email:
                # Email address has been changed - send a confirmation email to the new
                # address and  a password reset to the old email address link in case this is a
                # suspicious change.
                #change email_confirmed to False to enforce the user to re-confirm his new email address
                user_profile = new_user.get_profile()
                #get list_id from the old profile before the change
                list_id = settings.MAILCHIMP_LISTS[settings.MAILCHIMP_LIST_USERS]
                current_group_id = get_mailchimp_group_id(new_user, list_id, user_profile)
                user_profile.email_confirmed = False
                user_profile.save()
                ctx = {
                    'user': self.request.user,
                    'reset_url': get_password_reset_url(old_user),
                    'new_email': new_email,
                }
                msgs = CommunicationEventType.objects.get_and_render(
                    code=self.communication_type_code, context=ctx)
                Dispatcher().dispatch_user_messages(old_user, msgs)
                #send confirmation message and add on-site notification
                senders.send_email_confirmation_email(new_user)
                senders.add_email_confirmation_notification(new_user)

                #move user to the email unconfirmed list
                new_group_id = get_mailchimp_group_id(new_user, list_id, user_profile)
                group_settings = {
                   current_group_id: False,
                   new_group_id: True
                }

                subscribe_user.apply_async(
                    kwargs={
                        'user': new_user,
                        'list_id': list_id,
                        'group_settings': group_settings,
                        'is_conf_url_required': True
                    },
                    countdown=60 * 10, #wait 10 minutes to avoid errors on mailchimp's end
                    queue='analytics'
                )
                messages.info(self.request, _("Your email address has been changed, confirmation message was sent"
                                              " to <strong>%s</strong>."
                                            % new_email), extra_tags='safe')
            return self.json_response(
                is_valid=True,
                redirect_url=self.get_success_url()
            )
        return HttpResponseRedirect(reverse('customer:profile-view'))

    def form_invalid(self, form):
        if self.request.is_ajax():
            ctx = {'form': form}
            return self.json_response(ctx=ctx)
        return HttpResponseRedirect(reverse('customer:profile-view'))


class AccountRegistrationView(CoreAccountRegistrationView, RegisterSessionData):
    via_homepage = False

    def dispatch(self, request, *args, **kwargs):
        if 'homepage_create_account' in request.POST:
            self.via_homepage = True
        self.register_session_data = RegisterSessionData(request)
        return super(AccountRegistrationView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if operation_suspended(request.POST.get('email')):
            return HttpResponseNotFound()
        return super(AccountRegistrationView, self).post(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        #we save the register_type in session here for social networks registration
        register_type = request.GET.get('register_type', 'organic')
        self.register_session_data.store_account_data(data={'register_type': register_type})
        return super(AccountRegistrationView, self).get(request, *args, **kwargs)

    def form_valid(self, form):
        #check for spammers
        check_honeypot(self.request)
        account_data = self.register_session_data.get_account_data()
        account_data.update({
            'first_name': form.cleaned_data.get('first_name', ''),
            'last_name': form.cleaned_data.get('last_name', ''),
            'email': form.cleaned_data['email'],
            'password': form.cleaned_data['password1'],
            'username': generate_username(),
        })
        #user has completed the sign up form so we have everything set
        #for him, need to mark this to bypass the pp and tos checkbox
        account_data['terms_accepted'] = not self.via_homepage
        self.register_session_data.store_account_data(data=account_data)
        return HttpResponseRedirect(form.cleaned_data['redirect_url'])

    def get_form_kwargs(self):
        """
        special support for signing in through the homepage
        where the user only enters his email address and password
        we need to set first name and last name fields as not required
        """
        kwargs = super(AccountRegistrationView, self).get_form_kwargs()
        kwargs['initial'] = {'redirect_url': reverse('customer:register-settings')}
        return kwargs


class AccountAuthView(CoreAccountAuthView):
    def post(self, request, *args, **kwargs):
         #check for spammers
        check_honeypot(request)
        return super(AccountAuthView, self).post(request, *args, **kwargs)

    def get_context_data(self, *args, **kwargs):
        ctx = super(CoreAccountAuthView, self).get_context_data(**kwargs)
        ctx.update(kwargs)
        # Don't pass request as we don't want to trigger validation of BOTH
        # forms.
        if 'login_form' not in kwargs:
            ctx['login_form'] = self.get_login_form()
        return ctx


class EmailHistoryView(CoreEmailHistoryView):
    http_method_names = ['get']
    def get(self, request, *args, **kwargs):
        """
        We don't support email history page, return 404
        """
        raise Http404
    #def get_queryset(self):
    #    """Return a customer's orders"""
    #    return Email._default_manager.filter(user=self.request.user).order_by('-date_sent')

class EmailDetailView(CoreEmailDetailView):
    http_method_names = ['get']
    def get(self, request, *args, **kwargs):
        """
        We don't support email detail page, return 404
        """
        raise Http404


class ProfileView(FormView):
    form_class = ProfileForm
    service_name = None

    def dispatch(self, request, *args, **kwargs):
        self.profile = request.user.get_profile()
        #check for exclusive club data
        uidb36 = kwargs.pop('uidb36', None)
        token =  kwargs.pop('token', None)
        encoded_club = kwargs.pop('club', None)

        if uidb36 and token and encoded_club:
            try:
                uid_int = base36_to_int(uidb36)
                User.objects.get(id=uid_int)
            except (ValueError, User.DoesNotExist):
                pass
            else:
                user_qualified_for_exclusive_club = self.profile.get_exclusive_club()
                if user_qualified_for_exclusive_club and\
                        tokens.exclusive_club_token_generator.check_token(request.user, token, encoded_club):
                    self.join_exclusive_club(request)
                else:
                    messages.error(request, "Joining Purse.io exclusive club has failed.<br>"
                                            "Please contact customer support.",
                                   extra_tags='safe')

        #check if account setup didn't complete and redirect
        if not self.profile.is_account_setup_completed:
            return HttpResponseRedirect(reverse('customer:account-setup'))
        self.is_affiliate = request.user.get_profile().is_affiliate_account()
        return super(ProfileView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        """
        Handle extra services order from CTA
        """
        type = request.GET.get('type')
        if type is not None and type == 'order_extra_services_cta':
            service = request.GET.get('service')
            if service:
                self.service_name = service
                self.set_extra_service()
        return super(ProfileView, self).get(request, *args, **kwargs)

    def join_exclusive_club(self, request):
        self.profile.qualified_for_exclusive_club_offers = True
        self.profile.save()
        messages.success(request, "Roger that! You've successfully joined the Purse.io exclusive club.<br>"
                                  "Club's offers will be applied automatically at checkout.",
                        extra_tags='safe')

    def post(self, request, *args, **kwargs):
        club_name = request.POST.get('club-name')
        if club_name:
            qualified_exclusive_club = self.profile.get_exclusive_club()
            if qualified_exclusive_club and qualified_exclusive_club.lower() == club_name.lower():
                self.join_exclusive_club(request)
            else:
                messages.error(request, "Joining Purse.io exclusive club has failed.<br>"
                                        "Please contact customer support.",
                               extra_tags='safe')
            return HttpResponseRedirect(reverse('customer:profile-view'))
        return super(ProfileView, self).post(request, *args, **kwargs)

    def translate_extra_service_to_field(self):
        if self.service_name == 'customs_declaration':
            field_name, field_val = 'is_filling_customs_declaration', True
            self.service_name = 'Customs Declaration Paperwork'
        elif self.service_name == '1_photo':
            field_name, field_val = 'is_photos', 'One'
            self.service_name = '1 Package Content Photo'
        elif self.service_name == '3_photos':
            field_name, field_val = 'is_photos', 'Three'
            self.service_name = '3 Package Content Photos'
        elif self.service_name == 'package_consolidation':
            field_name, field_val = 'is_consolidate_every_new_package', True
            self.service_name = 'Package Consolidation'
        else:
            field_name, field_val = None, None
        return field_name, field_val

    def set_extra_service(self):
        field_name, field_val = self.translate_extra_service_to_field()
        if field_name is not None and field_val is not None:
            # track this event in mixpanel
            mixpanel_track_academy_extra_service_order.apply_async(
                kwargs={'user_id': self.request.user.id, 'service': self.service_name},
                queue='analytics')
            if getattr(self.profile, field_name, False) != field_val:
                setattr(self.profile, field_name, field_val)
                self.profile.save()
        else:
            self.service_name = None

    def count_response_action(self, action):
        return ReferralResponse.objects.filter(
            referral__user=self.request.user,
            action=action).count()

    def get_template_names(self):
        if self.is_affiliate:
            return ['customer/affiliate/profile.html']
        return ['customer/profile/profile.html']

    def get_personal_context_data(self, **kwargs):
        profile = self.profile
        ctx = {}
        warehouse_address_list = user_utils.get_warehouse_address()
        http_referer = self.request.META.get('HTTP_REFERER', '')
        ctx['email_confirmed'] = profile.email_confirmed
        ctx['virtual_addresses'] = profile.generate_virtual_addresses(warehouse_address_list)
        ctx['addresses'] = self.get_user_addresses()
        ctx['orders'] = self.get_latest_user_orders()
        ctx['notifications'] = self.get_latest_user_notifications()
        ctx['account_status'] = self.get_account_status(profile)
        ctx['is_affiliate'] = profile.is_affiliate_account()
        ctx['tour_played'] = profile.tour_started
        ctx['hide_us_address'] = profile.hide_us_address()
        ctx['operation_shut_down'] = operation_shut_down(self.request.user)
        ctx['show_exclusive_club_popup'] = profile.qualified_for_exclusive_club_offers
        ctx['after_register'] = 'register/services' in http_referer or 'accounts/setup' in http_referer
        if self.service_name:
            ctx['service_name'] = self.service_name
        return ctx

    def get_affiliate_context_data(self, **kwargs):
        profile = self.profile
        ctx = {}
        ctx['email_confirmed'] = profile.email_confirmed
        ctx['notifications'] = self.get_latest_user_notifications()
        ctx['link_clicked_count'] = self.count_response_action('RESPONDED')
        ctx['link_signed_up_count'] = self.count_response_action('USER_SIGNUP')
        ctx['future_package_delivery_credit'] = ctx['link_signed_up_count'] * \
                                                settings.AFFILIATE_PROGRAM_CREDITS['PACKAGE_DELIVERY']
        ctx['total_unredeemed_credit'] = profile.referral_unredeemed_credit()
        ctx['total_redeemed_credit'] = profile.referral_redeemed_credit()
        ctx['affiliate_link'] = profile.affiliate_link
        return ctx

    def get_context_data(self, **kwargs):
        ctx = super(ProfileView, self).get_context_data(**kwargs)
        if self.is_affiliate:
            ctx.update(self.get_affiliate_context_data())
        else:
            ctx.update(self.get_personal_context_data())
        return ctx

    def get_account_status(self, profile):
        try:
            return profile.account_status
        except ObjectDoesNotExist:
            return None

    def get_latest_user_orders(self):
        """
        Return latest 5 placed orders
        """
        return Order._default_manager.filter(
            user=self.request.user)\
            .exclude(status__in=['Pending', 'Cancelled'])\
            .order_by('-date_placed')[:5]

    def get_latest_user_notifications(self):
        """
        Return latest 5 notifications
        """
        return Notification._default_manager.filter(
                recipient=self.request.user,
                location=Notification.INBOX).order_by('-date_sent')[:3]

    def get_user_addresses(self):
        """
        Return 3 shipping addresses including the default shipping
        addresses first and then by number of orders placed with a given address
        """
        return UserAddress._default_manager.filter(
            user=self.request.user).order_by(
            '-is_default_for_shipping', '-num_orders')[:3]

    def get_form_kwargs(self):
        kwargs = super(ProfileView, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_profile(self, user):
        profile_class = get_profile_class()
        try:
            profile = profile_class.objects.select_related(
                'account_status').get(user=user)
        except ObjectDoesNotExist:
            profile = profile_class(user=user)
        return profile

    def get_success_url(self):
        return reverse('customer:profile-view')

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _("Changes saved"))
        return super(ProfileView, self).form_valid(form)


class SettingsView(ProfileView):
    pass


class ExtraServicesHandlingView(ProductCache, AjaxTemplateMixin,
                                PendingPackagesMixin, FormView):
    form_class = SpecialRequestsForm
    ajax_template_name = 'customer/package/extra_services_inner.html'
    FILTER_STATUSES = None
    package = None

    def dispatch(self, request, *args, **kwargs):
        package_pk = kwargs.get('package_pk')
        self.package = self.get_package_from_db(package_pk)
        if self.package.is_waiting_for_consolidation:
            self.FILTER_STATUSES =  ['waiting_for_consolidation', 'predefined_waiting_for_consolidation']
        else:
            self.FILTER_STATUSES = ['pending', 'pending_returned_package']
        return super(ExtraServicesHandlingView, self).dispatch(request, *args, **kwargs)

    def get_package_from_db(self, pk):
        return Product.objects.filter(pk=pk).select_related('special_requests').get()

    def get_special_requests_instance(self):
        try:
            instance = self.package.special_requests
        except ProductSpecialRequests.DoesNotExist:
            instance = None
        return instance

    def get_form_kwargs(self):
        kwargs = super(ExtraServicesHandlingView, self).get_form_kwargs()
        kwargs['package'] = self.package
        kwargs['instance'] = self.get_special_requests_instance()
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super(ExtraServicesHandlingView, self).get_context_data(**kwargs)
        ctx['package'] = self.package
        return ctx

    def is_express_checkout_needed(self, special_req):
        return special_req.is_express_checkout and not special_req.express_checkout_done

    def is_offline_work_needed(self, special_req):
        return len(special_req.pending_special_requests(include_express_checkout=False)) > 0

    def new_services_ordered(self, special_req):
        return len(special_req.pending_special_requests(include_express_checkout=True)) > 0

    def validate_account_status(self, profile):
        if profile.account_verification_in_process():
            return _("You can't order any extra service while we're reviewing your documents.")
        elif profile.account_verification_required():
            return _("There is a pending verification request on your account.<br/>"
                      "You must <a href='%s'>verify</a> your account before you can order"
                      " any extra service for your packages." % reverse('customer:account-verify',
                      kwargs={'pk': profile.account_status.pk}))
        elif profile.account_verification_requires_more_docs():
            return _("We're waiting for additional documents to complete your"
                     " account verification process.")
        else:
            return _("We couldn't verify your account.<br/>"
                     "You can only return your packages back to the senders.<br/>"
                     "Follow through this <a href='%stutorial/#tutorial-q3'>tutorial</a> for"
                     " a detailed guide." % reverse('faq'))

    def validate_additional_receiver(self, package):
        receiver_name = package.additional_receiver.get_full_name()
        if self.package.receiver_verification_required():
            return _("%(name)s is not a verified receiver.<br/>Please"
                    " <a href='%(verify_url)s'>verify</a> this receiver through"
                    " your control panel before ordering any extra service." % {
                    'name': receiver_name,
                    'verify_url': reverse('customer:additional-receiver-verify',
                                          kwargs={'pk': self.package.additional_receiver.pk})})
        elif self.package.receiver_verification_in_process():
            return _("You can't order any extra service while we're reviewing"
                     " the additional receiver's documents.")
        elif self.package.receiver_verification_requires_more_docs():
            return _("We're waiting for additional documents to complete"
                     " the verification process of %s." % receiver_name)
        else:
            return _("We couldn't verify %s identity.<br/>"
                     "You can only return this package back to the sender.<br/>"
                     "Follow through this <a href='%stutorial/#tutorial-q3'>tutorial</a> for"
                     " a detailed guide." % (receiver_name, reverse('faq')))

    def form_valid(self, form):
        if self.request.is_ajax():
            flash_messages = ajax.FlashMessages()
            special_request = form.save(commit=False)
            profile = self.request.user.get_profile()

            if not profile.account_verified():
                err_msg = self.validate_account_status(profile)
                flash_messages.error(err_msg)
            elif not self.package.receiver_verified():
                err_msg = self.validate_additional_receiver(self.package)
                flash_messages.error(err_msg)
            elif not profile.email_confirmed:
                flash_messages.error(_("You must <a href='%s'>confirm</a> your email address before you can"
                                       " order any extra service." % reverse('customer:email-confirmation-send')))
            elif self.package.is_contain_prohibited_items:
                flash_messages.error(_("Your package contains prohibited items that can't be exported internationally.<br/>"
                                          "You can only return this package back to the sender.<br/>"
                                          "Follow through this <a href='%stutorial/#tutorial-q3'>tutorial</a> for"
                                          " a detailed guide." % reverse('faq')))
            elif not self.new_services_ordered(special_request):
                #no new special requests
                flash_messages.info(_("You haven't ordered any new extra services."))
            else:
                #show success message to customer
                if self.is_offline_work_needed(special_request):
                    flash_messages.success(_("Extra Services order has been successfully received."
                                             "We will notify you once processing is complete."))
                    #change package status to handling_special_requests
                    #save old status in cache to apply when special requests completed
                    self.store_product_status(key="%s_status" % self.package.upc, status=self.package.status)
                    self.package.status = 'handling_special_requests'
                    self.package.save()
                    #send notification to customer
                    self.send_product_status_change_alert(self.package)
                #only express checkout is online special request
                #no action needed on such request
                else:
                    flash_messages.success(_("Done - expedite package processing is set for your package."))
                #special handling for express checkout where we need to create
                #the fee over here since we immediately mark that express checkout is done
                #since no action is required by the operations staff
                if self.is_express_checkout_needed(special_request):
                    special_request.express_checkout_done = True
                    #only express checkout selected, need to create fee right here
                    charge = D('0.00') if 'express_checkout' in profile.get_exclusive_club_services_offer() else\
                             settings.EXPRESS_CHECKOUT_CHARGE
                    catalogue_utils.create_fee(
                        settings.EXPRESS_CHECKOUT_TEMPLATE % self.package.upc,
                        _("Express Checkout"),
                        self.package,
                        charge,
                        'special_requests',
                        'special_requests_fee')
                special_request.save()

            self.template_name = 'customer/package/packages_details.html'
            ctx = {}
            pending_packages = self.get_packages(self.request.user)
            redirect_url = ''
            if not pending_packages.exists():
                #no pending packages exist need to redirect to main control
                #panel page to show modal message
                #flash_messages.apply_to_request(self.request)
                redirect_url = reverse('customer:profile-view') + '?extra-services=true'
            else:
                ctx['pending_packages'] = pending_packages
                if self.package.is_waiting_for_consolidation:
                    ctx['consolidate'] = True
            return self.json_response(
                    ctx=ctx,
                    flash_messages=flash_messages,
                    is_valid=True,
                    redirect_url=redirect_url
            )
        return HttpResponseRedirect(reverse('customer:profile-view'))

    def form_invalid(self, form):
        if self.request.is_ajax():
            ctx = {
                'form': form,
                'package': self.package
            }
            self.template_name = self.ajax_template_name
            return self.json_response(ctx=ctx, is_valid=False)
        return HttpResponseRedirect(reverse('customer:profile-view'))


class PendingPackagesView(PageTitleMixin, PendingPackagesMixin, TemplateView):
    template_name = 'customer/package/pending_packages.html'
    page_title = _('Incoming Packages')
    active_tab = 'pending_packages'
    FILTER_STATUSES = ['pending', 'pending_returned_package']

    def get_context_data(self, **kwargs):
        ctx = super(PendingPackagesView, self).get_context_data(**kwargs)
        ctx['pending_packages'] = self.get_packages(self.request.user)
        return ctx

    def get_success_url(self):
        """
        redirect to main control panel page if no pending packages exists
        else redirect to pending packages page
        """
        pending_packages = self.get_packages(self.request.user)
        if not pending_packages.exists():
            success_url = reverse('customer:profile-view')
        else:
            success_url = reverse('customer:pending-packages')
        return success_url

    def get(self, request, *args, **kwargs):
        pending_packages = self.get_packages(self.request.user)
        if not pending_packages.exists() or operation_shut_down(self.request.user):
            #no pending packages exist need to redirect to main control
            return HttpResponseRedirect(reverse('customer:profile-view'))
        return super(PendingPackagesView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action', '')
        package_id = request.POST.get('product_id', None)

        if action == 'consolidation_add':
            package = get_object_or_404(Product, id=package_id)
            #this action is not allowed if the additional receiver exists and the
            #verification process failed, or when the account verification failed
            profile = request.user.get_profile()
            if profile.account_verification_failed():
                messages.error(request, _("We couldn't verify your account.<br/>"
                                          "You can only return your packages back to the senders.<br/>"
                                          "Follow through this <a href='%stutorial/#tutorial-q3'>tutorial</a> for"
                                          " a detailed guide." % reverse('faq')),
                               extra_tags='safe')
                return HttpResponseRedirect(reverse('customer:pending-packages'))
            elif package.receiver_verification_failed():
                receiver_name = package.additional_receiver.get_full_name()
                messages.error(request, _("We couldn't verify %s identity.<br/>"
                          "You can only return this package back to the sender.<br/>"
                          "Follow through this <a href='%stutorial/#tutorial-q3'>tutorial</a>"
                          " for a detailed guide." % (receiver_name, reverse('faq'))),
                               extra_tags='safe')
                return HttpResponseRedirect(reverse('customer:pending-packages'))
            elif not profile.email_confirmed:
                messages.error(request, _("You must <a href='%s'>confirm</a> your email address before you can"
                                          " request this action.") %
                                            reverse('customer:email-confirmation-send'),
                               extra_tags='safe block')
                return HttpResponseRedirect(reverse('customer:pending-packages'))
            elif package.is_contain_prohibited_items:
                messages.error(request, _("Your package contains prohibited items that can't be exported internationally.<br/>"
                                          "You can only return this package back to the sender.<br/>"
                                          "Follow through this <a href='%stutorial/#tutorial-q3'>tutorial</a> for"
                                          " a detailed guide." % reverse('faq')),
                               extra_tags='safe')
                return HttpResponseRedirect(reverse('customer:pending-packages'))
            else:
                #change package status to reflect that it is waiting for consolidation
                package.status = 'waiting_for_consolidation'
                package.save()
                #send notification to customer
                #self.send_product_status_change_alert(package)
                #display success message to user
                messages.success(request, _("Package successfully moved to the Package Consolidation section."))
                return HttpResponseRedirect(self.get_success_url())
        else:
            #unknown form type, display error and redirect to account:summary
            messages.error(request, _("Unsupported action."))
            return HttpResponseRedirect(reverse('customer:profile-view'))


class WaitingForConsolidationPackagesView(PageTitleMixin, PendingPackagesMixin, TemplateView):
    template_name = 'customer/package/waiting_for_consolidation_packages.html'
    page_title = _('Package Consolidation')
    active_tab = 'packages_to_consolidate'
    consolidation_requests_form = ConsolidationRequestForm
    FILTER_STATUSES = ['waiting_for_consolidation', 'predefined_waiting_for_consolidation']

    def get(self, request, *args, **kwargs):
        if operation_shut_down(self.request.user):
           return HttpResponseRedirect(reverse('customer:profile-view'))
        return super(WaitingForConsolidationPackagesView, self).get(request, *args, **kwargs)

    def is_consolidation_requests_submitted(self):
        """
        Check if there's POST data that matches consolidationRequestsForm field names
        """
        fields = dict(self.consolidation_requests_form.base_fields.items() +
                      self.consolidation_requests_form.declared_fields.items())
        for name, field in fields.iteritems():
            if len(self.request.POST.get(name, '')) > 0:
                return True
        return False

    def get_consolidation_requests_form(self, package=None):
        """
        Get the the ``ConsolidationRequestsForm`` prepopulated with POST
        data if available. If the product in this view has a
        special requests model it will be passed into the form as
        ``instance``.
        """
        try:
            consolidation_requests = package.consolidation_requests
        except (AttributeError, ProductConsolidationRequests.DoesNotExist):
            # either self.object is None, or no special_requests
            consolidation_requests = None
        return self.consolidation_requests_form(
            data=self.request.POST if self.is_consolidation_requests_submitted() else None,
            instance=consolidation_requests)

    def get_context_data(self, **kwargs):
        ctx = super(WaitingForConsolidationPackagesView, self).get_context_data(**kwargs)
        ctx['pending_packages'] = self.get_packages(self.request.user)
        ctx['consolidation_requests_form'] = self.get_consolidation_requests_form()
        return ctx

    def packages_belong_to_one_partner(self, packages):
        """
        packages len is >= 2
        """
        partner_name = packages[0].partner.name
        for package in packages:
            if partner_name != package.partner.name:
                return False
        return True

    def find_package_with_prohibited_items(self, inner_packages):
        for package in inner_packages:
            if package.is_contain_prohibited_items:
                return package
        return None

    def get_battery_status(self, inner_packages):
        battery_status = Product.NO_BATTERY
        for package in inner_packages:
            if package.battery_status == Product.LOOSE_BATTERY:
                battery_status =  Product.LOOSE_BATTERY
                break
            if package.battery_status == Product.INSTALLED_BATTERY:
                battery_status = Product.INSTALLED_BATTERY
        return battery_status

    def all_additional_receivers_verified(self, children_packages):
        for child_package in children_packages:
            if not child_package.receiver_verified():
                #additional receiver is not verified, don't accept this request
                receiver_name = child_package.additional_receiver.get_full_name()
                if child_package.receiver_verification_required():
                    messages.error(self.request,
                                   _("%(name)s is not a verified receiver.<br/>Before you can complete the Package"
                                    " Consolidation request you must <a href='%(verify_url)s'>verify</a> this receiver through"
                                    " your control panel." % {
                                       'name': child_package.additional_receiver.get_full_name(),
                                       'verify_url': reverse('customer:additional-receiver-verify',
                                                    kwargs={'pk': child_package.additional_receiver.pk})}),
                                    extra_tags='safe block')
                    return False
                elif child_package.receiver_verification_in_process():
                    messages.error(self.request, _("You can't complete the Package Consolidation request while"
                                                   " we're reviewing %s's documents." % receiver_name))
                    return False
                elif child_package.receiver_verification_requires_more_docs():
                    messages.error(self.request, _("We're waiting for additional documents to complete"
                                                 " the verification process of %s." % receiver_name))
                    return False
                else:
                    messages.error(self.request,
                                   _("We couldn't verify %s identity, please <a href='%s'>contact</a>"
                                     " customer support for more details.") % (
                                       receiver_name, reverse('contact')),
                                   extra_tags='safe block')
                    return False
        return True

    def account_verified(self, profile):
        if not profile.account_verified():
            if profile.account_verification_in_process():
                messages.error(self.request,
                               _("You can't complete the Package Consolidation request while we're reviewing"
                                " your documents."))
                return False
            elif profile.account_verification_required():
                messages.error(self.request,
                               _("There is a pending verification request on your account.<br/>"
                               "You must <a href='%s'>verify</a> your account before you can complete"
                               " the Package Consolidation request.") % reverse('customer:account-verify',
                                        kwargs={'pk': profile.account_status.pk}),
                               extra_tags='safe block')
                return False
            elif profile.account_verification_requires_more_docs():
                messages.error(self.request, _("We're waiting for additional documents to complete your"
                                               " account verification process."))
                return False
            else:
                messages.error(self.request,
                               _("We couldn't verify your account.<br/>"
                                 "You can only return your packages back to the senders.<br/>"
                                 "Follow through this <a href='%stutorial/#tutorial-q3'>tutorial</a> for"
                                 " a detailed guide." % reverse('faq')),
                               extra_tags='safe block')
                return False
        return True

    def get_shopify_store_id_and_zipcode(self, inner_packages):
        for package in inner_packages:
            if package.shopify_store_id:
                return package.shopify_store_id, package.merchant_zipcode
        return None, None

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action', '')
        if action == 'consolidation_done':
            profile = request.user.get_profile()
            #user has finished adding package to consolidate
            #make sure the account is verified before we proceed with the consolidation request
            if not self.account_verified(profile):
                return HttpResponseRedirect(reverse('customer:waiting-for-consolidation-packages'))

            if not profile.email_confirmed:
                messages.error(request, _("You must <a href='%s'>confirm</a> your email address before you can"
                                          " order the Package Consolidation service." %
                                          reverse('customer:email-confirmation-send')))

            qs_predefined_children = Product.packages.prefetch_related(
                'stockrecords', 'stockrecords__partner').filter(
                owner=request.user, status='predefined_waiting_for_consolidation')
            qs_non_predefined_children = Product.packages.prefetch_related(
                'stockrecords', 'stockrecords__partner').filter(
                owner=request.user, status='waiting_for_consolidation')

            qs_non_predefined_children_list = list(qs_non_predefined_children)
            children = list(qs_predefined_children) + qs_non_predefined_children_list

            if not children:
                messages.error(request, _("You don't have any packages to consolidate."))
                return HttpResponseRedirect(reverse('customer:profile-view'))

            #make sure user tries to consolidate more than 1 package
            if len(children) == 1:
                messages.warning(request, _("You can't consolidate only 1 package, please add more packages."))
                return HttpResponseRedirect(reverse('customer:waiting-for-consolidation-packages'))

            #make sure all packages were processed by the same partner
            if not self.packages_belong_to_one_partner(children):
                messages.warning(request, _("You can't consolidate packages stored in different warehouses.<br/>"
                                            "Please contact customer support."), extra_tags='safe')
                return HttpResponseRedirect(reverse('customer:waiting-for-consolidation-packages'))

            #make sure all additional receivers are verified (if any)
            if not self.all_additional_receivers_verified(children):
                return HttpResponseRedirect(reverse('customer:waiting-for-consolidation-packages'))

            #make sure packages don't contain prohibited items
            package_with_prohibited_items = self.find_package_with_prohibited_items(children)
            if package_with_prohibited_items:
                messages.warning(request, _("Package #%s contains prohibited item(s) that can't be exported"
                                            " internationally.<br/>"
                                            "Remove it from the list and send it back to the sender." %
                                            package_with_prohibited_items),
                                 extra_tags='safe')
                return HttpResponseRedirect(reverse('customer:waiting-for-consolidation-packages'))

            #make sure the user doesn't have a pending consolidated package
            #if so, he would need to first release it for delivery and then we could take his request
            #pending_consolidated_packages = Product.packages\
            #    .filter(owner=request.user, combined_products__isnull=False)\
            #    .exclude(status__in=['paid', 'postage_purchased', 'shipped'])\
            #    .distinct()
            #if pending_consolidated_packages.exists():
            #    messages.warning(request, _("You have a pending consolidated package, you must release it for"
            #                                " delivery before you can request a new package consolidation."))
            #    if Product.packages\
            #            .filter(owner=request.user,
            #                    status__in=['pending', 'pending_returned_package'])\
            #            .exists():
            #        return HttpResponseRedirect(reverse('customer:pending-packages'))
            #    else:
            #        return HttpResponseRedirect(reverse('customer:profile-view'))

            #express checkout is a special extra service since no work has already done so
            #we need to take out the express checkout from all inner packages
            #predefined waiting for consolidation packages don't include the express checkout fee as it is forbidden
            for waiting_for_consolidation_package in qs_non_predefined_children_list:
                waiting_for_consolidation_package.variants.filter(upc__startswith='express_checkout_').delete()

            #need to create product with all "waiting consolidation" products as his children
            package_product_class = get_object_or_404(ProductClass, name='package')
            #create new product which consolidate children packages
            large_package = Product(
                upc=catalogue_utils.generate_upc(),
                owner=request.user,
                product_class=package_product_class,
                status='consolidation_taking_place',
                condition='Perfect',
                is_client_id_missing=False,
                battery_status=self.get_battery_status(children)
            )

            #get e-shops names from children and set as title
            large_package.title = large_package.create_consolidated_package_title(children)
            # set shopify shop id and merchant zipcode taken from the children
            # assumption: the consolidated box contains 1 package coming from shopify store at most
            large_package.shopify_store_id, large_package.merchant_zipcode = self.get_shopify_store_id_and_zipcode(children)
            # take zip code from the first child if not exists
            if not large_package.merchant_zipcode:
                large_package.merchant_zipcode = children[0].merchant_zipcode
            #Attributes
            setattr(large_package.attr, 'weight', 0.0)
            setattr(large_package.attr, 'height', 0.0)
            setattr(large_package.attr, 'width',  0.0)
            setattr(large_package.attr, 'length', 0.0)
            setattr(large_package.attr, 'is_envelope', False)
            large_package.save()
            #calculate date created based on the first arrival time among all children
            #we need to do it after we save the product as the date_created field is marked with
            #auto_now_add which sets the date_created field value to current time when the object
            #is first created, therefore we save the object and them modify this value and save it again
            large_package.date_created = large_package.calculate_date_created(children)
            large_package.save()

            #Take partner from children list and create a stockrecord for large package
            children_partner = children[0].partner
            create_package_stock_record(package=large_package, partner=children_partner)

            #process predefined extra services
            catalogue_utils.process_consolidated_package_predefined_special_request(large_package)

            #change children status to "packed" and add them to the newly created product
            #link to large package
            large_package.combined_products.add(*children)
            qs_predefined_children.update(status='predefined_packed')
            qs_non_predefined_children.update(status='packed')

            consolidation_requests_form = self.get_consolidation_requests_form(large_package)
            if consolidation_requests_form.is_valid():
                consolidation_requests = consolidation_requests_form.save(commit=False)
                consolidation_requests.package = large_package
                consolidation_requests.save()

            #display success message to user
            #messages.success(request, _("We've successfully received your package consolidation request. "
            #                            "We will email you as soon as your request is completed and ready for shipment."))
            return HttpResponseRedirect(reverse('customer:profile-view') + '?package-consolidation=true')
        #elif action == 'take_measures':
        #    package = get_object_or_404(Product, id=package_id)
        #    #waiting for consolidation return to store - need to take measures
        #    package.status = 'take_measures'
        #    package.save()
        #    #send notification to customer
        #    self.send_product_status_change_alert(package)
        #    #display success message to user
        #    messages.success(request, _("We've successfully received your request."
        #                                "We will email you once we are done processing your request."))
        #    return HttpResponseRedirect(reverse('customer:waiting-for-consolidation-packages'))
        elif action == 'consolidation_remove':
            package_id = request.POST.get('product_id', None)
            #change package status back to pending
            package = get_object_or_404(Product, id=package_id)
            package.status = 'pending'
            package.save()
            messages.success(request, _("Package successfully removed from the Package Consolidation section."))
            return HttpResponseRedirect(self.get_success_url())
        else:
            #unknown form type, display error and redirect to account:summary
            messages.error(request, _("Unsupported action."))
            return HttpResponseRedirect(reverse('customer:profile-view'))

    def get_success_url(self):
        """
        redirect to main control panel page if no waiting for consolidation packages exists
        else redirect to waiting for consolidation page packages page
        """
        waiting_for_consolidation_packages = self.get_packages(self.request.user)
        if not waiting_for_consolidation_packages.exists():
            success_url = reverse('customer:profile-view')
        else:
            success_url = reverse('customer:waiting-for-consolidation-packages')
        return success_url

class RegisterProfileView(RegisterUserMixin, FormView, RegisterSessionData):
    form_class = ProfileWithEmailForm
    user_extra_data = None
    template_name = 'customer/registration_profile.html'

    def dispatch(self, request, *args, **kwargs):
        self.register_session_data = RegisterSessionData(request)
        self.register_data = self.register_session_data.get_account_data()
        return super(RegisterProfileView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated():
            return HttpResponseRedirect(reverse('customer:profile-view'))
        if not self.register_data:
            referrer = request.META.get('HTTP_REFERER', 'N/A')
            logger.critical("register data could not be loaded from session, referrer = %s, session_key = %s",
                            referrer, request.session.session_key)
            messages.error(self.request, _("Something went wrong, please try again."))
            return HttpResponseRedirect(reverse('customer:register'))
        self.capture_potential_user_email(self.register_data.get("email", ''))
        return super(RegisterProfileView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        #get user location
        self.user_extra_data = self.get_user_extra_data(request)
        #get a copy of the POST data
        self.post_data = copy.deepcopy(request.POST)
        self.align_photos_service()
        return super(RegisterProfileView, self).post(request, *args, **kwargs)

    def get_initial(self):
        initial = super(RegisterProfileView, self).get_initial()
        initial['email'] = self.register_data.get("email", '')
        initial['first_name'] = self.register_data.get("first_name", '')
        initial['last_name'] = self.register_data.get("last_name", '')
        return initial

    def get_context_data(self, **kwargs):
        ctx = super(RegisterProfileView, self).get_context_data(**kwargs)
        ctx['show_terms'] = not self.register_data.get('terms_accepted', False)
        return ctx

    def form_valid(self, form):
        #we have everything we need we can go on with the
        #creation of user and profile
        #pop out the terms_accepted attribute which is not
        #part of the user model
        self.register_data.pop('terms_accepted', None)
        register_type = self.register_data.pop('register_type', 'organic')
        #update attributes with the form data
        self.register_data['first_name'] = form.cleaned_data['first_name']
        self.register_data['last_name'] = form.cleaned_data['last_name']
        self.register_data['email'] = form.cleaned_data['email'].lower()
        #register and save user
        user = self.register_user(self.register_data)
        self.link_potential_user(user)
        #create profile
        profile = form.save(commit=False)
        profile.is_account_setup_completed = True
        profile.uuid = generate_uuid()
        profile.user = user
        profile.country = form.cleaned_data['country']
        if self.user_extra_data is not None:
            profile.city = self.user_extra_data['city']
            #profile.country = self.user_extra_data['country']
            profile.ip = self.user_extra_data['ip']
        profile.save()
        #raise registered signal for mixpanel processing to start
        user_registered.send_robust(sender=self, user=user,
                                    profile=profile,
                                    request=self.request,
                                    mixpanel_anon_id=form.cleaned_data.get('mixpanel_anon_id'),
                                    register_type=register_type)
        #clear session data
        self.register_session_data.delete_account_data()
        senders.add_new_registration_notification(user)
        self.add_tour_message()
        return HttpResponseRedirect(self.get_success_url())

    def get_success_response(self):
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        url = settings.LOGIN_REDIRECT_URL
        return url

    def get_form_kwargs(self):
        kwargs = {'initial': self.get_initial()}
        kwargs['ip_country'] = self.user_extra_data['country'] if self.user_extra_data else None
        if self.request.method in ('POST', 'PUT'):
            kwargs.update({
                'data': self.post_data,
                'files': self.request.FILES,
            })
        return kwargs


class APICompleteRegistrationView(RegisterUserMixin, FormView):
    form_class = ProfileWithEmailAndPasswordForm
    template_name = 'customer/registration_profile.html'
    issuer = None

    def dispatch(self, request, *args, **kwargs):
        uidb36 = kwargs.pop('uidb36', None)
        token =  kwargs.pop('token', None)
        encoded_issuer = kwargs.pop('issuer', None)
        validlink = True

        try:
            uid_int = base36_to_int(uidb36)
            self.user = User.objects.get(id=uid_int)
        except (ValueError, User.DoesNotExist):
            validlink = False
        else:
            profile = self.user.get_profile()
            if profile.is_account_setup_completed:
                return HttpResponseRedirect(reverse('customer:profile-view'))

        if not tokens.api_registration_token_generator.check_token(self.user, token, encoded_issuer):
            validlink = False

        if not validlink:
            messages.error(request, "Something went terribly wrong, please contact customer support.")
            return HttpResponseRedirect(reverse('customer:login'))

        #decode issuer
        self.issuer = base64.b64decode(encoded_issuer)
        return super(APICompleteRegistrationView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        #get user location
        self.user_extra_data = self.get_user_extra_data(request)
        #get a copy of the POST data
        self.post_data = copy.deepcopy(request.POST)
        self.align_photos_service()
        return super(APICompleteRegistrationView, self).post(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated():
            return HttpResponseRedirect(reverse('customer:profile-view'))
        #self.capture_potential_user_email(self.user.email)
        return super(APICompleteRegistrationView, self).get(request, *args, **kwargs)

    def get_initial(self):
        initial = super(APICompleteRegistrationView, self).get_initial()
        initial['email'] = getattr(self.user, "email", '')
        initial['first_name'] = getattr(self.user, "first_name", '')
        initial['last_name'] = getattr(self.user, "last_name", '')
        return initial

    def get_context_data(self, **kwargs):
        ctx = super(APICompleteRegistrationView, self).get_context_data(**kwargs)
        ctx['show_terms'] = False
        ctx['is_api_req'] = True
        return ctx

    def form_valid(self, form):
        register_data = {
            'first_name': form.cleaned_data['first_name'],
            'last_name': form.cleaned_data['last_name'],
            'password': form.cleaned_data['password'],
            'email': self.user.email
        }
        #register and save user
        user = self.register_user(register_data)
        #self.link_potential_user(user)
        #update profile
        profile = form.save(commit=False)
        profile.is_account_setup_completed = True
        profile.country = form.cleaned_data['country']
        if self.user_extra_data is not None:
            profile.city = self.user_extra_data['city']
            #profile.country = self.user_extra_data['country']
            profile.ip = self.user_extra_data['ip']
        profile.save()

        #raise registered signal for mixpanel processing to start
        user_registered.send_robust(sender=self, user=user,
                                    request=self.request,
                                    profile=profile,
                                    mixpanel_anon_id=form.cleaned_data.get('mixpanel_anon_id'),
                                    register_type=self.issuer)

        senders.add_new_registration_notification(user)
        self.add_tour_message()
        return HttpResponseRedirect(self.get_success_url())

    def get_success_response(self):
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        url = settings.LOGIN_REDIRECT_URL
        return url

    def get_form_kwargs(self):
        kwargs = {
            'initial': self.get_initial(),
            'instance': self.user.get_profile()
        }
        if self.request.method in ('POST', 'PUT'):
            kwargs.update({
                'data': self.post_data,
                'files': self.request.FILES,
            })
        return kwargs

class AccountSetupView(RegisterUserMixin, FormView):
    form_class = ProfileWithEmailForm
    template_name = 'customer/registration_profile.html'
    issuer = None

    def post(self, request, *args, **kwargs):
        #get user location
        self.user_extra_data = self.get_user_extra_data(request)
        #get a copy of the POST data
        self.post_data = copy.deepcopy(request.POST)
        self.align_photos_service()
        return super(AccountSetupView, self).post(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        if request.user.get_profile().is_account_setup_completed:
            return HttpResponseRedirect(reverse('customer:profile-view'))
        #self.capture_potential_user_email(self.user.email)
        return super(AccountSetupView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super(AccountSetupView, self).get_context_data(**kwargs)
        ctx['show_terms'] = False
        ctx['is_post_signup'] = True
        return ctx

    def get_form_kwargs(self):
        kwargs = super(AccountSetupView, self).get_form_kwargs()
        kwargs['bypass_email'] = True
        kwargs['instance'] = self.request.user.get_profile()
        kwargs['initial'] = {
            'first_name': self.request.user.first_name,
            'last_name': self.request.user.last_name,
            'email': self.request.user.email,
        }
        return kwargs

    def form_valid(self, form):
        #update profile
        profile = form.save(commit=False)
        profile.is_account_setup_completed = True
        profile.country = form.cleaned_data['country']
        if self.user_extra_data is not None:
            profile.city = self.user_extra_data['city']
            #profile.country = self.user_extra_data['country']
            profile.ip = self.user_extra_data['ip']
        profile.save()

        #raise registered signal for mixpanel processing to start
        user_registered.send_robust(sender=self, user=self.request.user,
                                    request=self.request,
                                    profile=profile,
                                    mixpanel_anon_id=form.cleaned_data.get('mixpanel_anon_id'),
                                    register_type=profile.registration_type)

        senders.add_new_registration_notification(self.request.user)
        self.add_tour_message()
        return HttpResponseRedirect(self.get_success_url())

    def get_success_response(self):
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        url = settings.LOGIN_REDIRECT_URL
        return url

#class CloseAccountView(LogoutView):
#    def get(self, request, *args, **kwargs):
#        #First make user inactive and then perform logout
#        user = request.user
#        user.is_active = False
#        user.save()
#        return super(CloseAccountView, self).get(request, *args, **kwargs)


class ShippingInsuranceClaimView(PageTitleMixin, FormView):
    form_class = ShippingInsuranceClaimForm
    page_title = _('Insurance Claim')
    active_tab = 'insurance_claim'
    template_name = "customer/insurance/insurance_claim.html"

    def get_form_kwargs(self):
        kwargs = super(ShippingInsuranceClaimView, self).get_form_kwargs()
        kwargs['owner'] = self.request.user
        return kwargs


    def form_valid(self, form):
        #mark that insurance claim was issued
        #send email with claim info and redirect with success message to
        #main control panel page
        order_num = form.cleaned_data['order_number']
        user = self.request.user
        order = user.orders.get(number=order_num)
        order.shipping_insurance_claim_issued = True
        order.save()
        self.send_insurance_claim_email(form)
        if not order.shipping_insurance:
            messages.success(self.request, _("Claim successfully received.<br/>"
                                     "You didn't insure your shipment, we will try to file a claim with"
                                     " the shipping carrier and notify you once we have further information."),
                             extra_tags='safe')
        else:
            messages.success(self.request, _("Claim successfully received.<br/>"
                                     "Customer support representative will contact"
                                     " you once we have further information."),
                             extra_tags='safe')
        return self.json_response(ctx=None, redirect_url=reverse('customer:profile-view'))

    def form_invalid(self, form):
        if self.request.is_ajax():
            ctx = {'form': form}
            return self.json_response(ctx)
        return super(ShippingInsuranceClaimView, self).form_invalid(form)

    def get_success_url(self):
        return reverse('customer:profile-view')

    def json_response(self, ctx, **kwargs):
        payload = kwargs
        if ctx:
            content_html = render_to_string(
                "customer/insurance/insurance_claim_form.html",
                RequestContext(self.request, ctx))
            payload['content_html'] = content_html
        return HttpResponse(json.dumps(payload),
                            mimetype="application/json")

    def get_context(self, form):
        ctx = {
            'message': form.cleaned_data['incident_details'],
            'order_num': form.cleaned_data['order_number'],
            'owner': self.request.user.get_full_name()
        }
        return ctx

    def send_insurance_claim_email(self, form):
        """
        Sends the message.
        """
        subject = "Shipping insurance claim"
        order_number = form.cleaned_data.get('order_number', '')
        from_email = settings.DEFAULT_FROM_EMAIL
        email_recipients = settings.SHIPPING_INSURANCE_CLAIM_EMAIL_RECIPIENTS
        ctx = Context(self.get_context(form))
        body_tpl = loader.get_template('customer/emails/insurance/'
                                        'insurance_claim_body.txt')


        #create zip file from all attachments
        files_to_zip = []
        invoice_file = form.cleaned_data.get('invoice')
        if invoice_file:
            #flush content to file
            path = default_storage.save(os.path.join(settings.MEDIA_ROOT, "insurance_claims", invoice_file.name),
                                        ContentFile(invoice_file.read()))
            files_to_zip.append(path)
        damaged_goods1_file = form.cleaned_data.get('damaged_goods1')
        if damaged_goods1_file:
            #flush content to file
            path = default_storage.save(os.path.join(settings.MEDIA_ROOT, "insurance_claims", damaged_goods1_file.name),
                                        ContentFile(damaged_goods1_file.read()))
            files_to_zip.append(path)
        damaged_goods2_file = form.cleaned_data.get('damaged_goods2')
        if damaged_goods2_file:
            #flush content to file
            path = default_storage.save(os.path.join(settings.MEDIA_ROOT, "insurance_claims", damaged_goods2_file.name),
                                        ContentFile(damaged_goods2_file.read()))
            files_to_zip.append(path)

        zipfile_name = "order#%s_%s.zip" % (order_number, time.strftime("%d-%m-%Y"))
        zipfile_path = os.path.join(settings.MEDIA_ROOT, "insurance_claims", zipfile_name)
        #create zip file
        if files_to_zip:
            create_zip_archive(files_to_zip, zipfile_path)

        mail.send(
            recipients=email_recipients,
            sender=from_email,
            subject=subject,
            message=body_tpl.render(ctx),
            priority='now',
            attachments={
                zipfile_name: zipfile_path
            }
        )

class AddressCreateView(CoreAddressCreateView):
    page_title = _('Add New Shipping Address')

    def get_form_kwargs(self):
        profile = self.request.user.get_profile()
        kwargs = super(AddressCreateView, self).get_form_kwargs()
        kwargs['is_merchant'] = False
        kwargs['is_business_account'] = profile.is_business_account()
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super(AddressCreateView, self).get_context_data(**kwargs)
        ctx['is_merchant'] = False
        ctx['action'] = reverse('customer:address-create')
        return ctx

    def get_success_url(self):
        #track add shipping address event
        mixpanel_track_create_shipping_address.apply_async(
            kwargs={'user_id': self.request.user.id}, queue='analytics')
        return super(AddressCreateView, self).get_success_url()

class AddressUpdateView(CoreAddressUpdateView):
    def get_form_kwargs(self):
        profile = self.request.user.get_profile()
        kwargs = super(AddressUpdateView, self).get_form_kwargs()
        kwargs['is_merchant'] = self.object.is_merchant
        kwargs['is_business_account'] = profile.is_business_account()
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super(AddressUpdateView, self).get_context_data(**kwargs)
        ctx['is_merchant'] = self.object.is_merchant
        ctx['action'] = reverse('customer:address-detail', kwargs={'pk': self.object.pk})
        return ctx


class AddressChangeStatusView(CoreAddressChangeStatusView):
    permanent = False

    def get_redirect_url(self):
        messages.success(self.request, _("Default shipping address was set successfully."))
        return self.request.META.get('HTTP_REFERER', reverse('customer:address-list'))


class AddressListView(CoreAddressListView):
    def get_queryset(self):
        qs = super(AddressListView, self).get_queryset()
        return qs.order_by('is_merchant', '-is_default_for_shipping')

class AddressDeleteView(AjaxTemplateMixin, CoreAddressDeleteView):
    def get_context_data(self, **kwargs):
        ctx = super(AddressDeleteView, self).get_context_data(**kwargs)
        ctx['pk'] = self.kwargs.get('pk')
        return ctx

    def post(self, *args, **kwargs):
        if self.request.is_ajax():
            super(AddressDeleteView, self).post(*args, **kwargs)
            redirect_url = self.request.POST.get('redirect_url', reverse('customer:address-list'))
            return self.json_response(
                is_valid=True,
                redirect_url=redirect_url
            )
        return HttpResponseRedirect(self.request.META.get('HTTP_REFERER', reverse('customer:address-list')))


class SendEmailConfirmationView(RedirectView):
    """
    Generate a email confirmation token and sends it out to the user
    """
    permanent = False
    url = reverse_lazy('customer:profile-view')

    def get(self, request, pk=None, action=None, *args, **kwargs):
        senders.send_email_confirmation_email(user=self.request.user, proactive=True)
        messages.success(request, _("Confirmation message was sent to <strong>%s</strong>."
                                    " Please check your email shortly and follow the instructions." %
                                    self.request.user.email), extra_tags='safe')
        return super(SendEmailConfirmationView, self).get(
            request, *args, **kwargs)

class ConfirmEmailConfirmationView(TemplateView):
    """
    View that checks the hash in a email confirmation link and redirects to main
    customer control panel page
    """
    template_name = "registration/email_confirmation_confirm.html"

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)

    @method_decorator(csrf_exempt)
    def post(self, request, *args, **kwargs):
        uidb36 =  self.kwargs.pop('uidb36', None)
        token =  self.kwargs.pop('token', None)
        validlink = False

        try:
            uid_int = base36_to_int(uidb36)
            user = User.objects.get(id=uid_int)
        except (ValueError, User.DoesNotExist):
            user = None

        #hash matched, change email_confirmed to True
        if user is not None and tokens.email_confirmation_token_generator.check_token(user, token):
            try:
                profile = user.get_profile()
            except ObjectDoesNotExist:
                pass
            else:
                if not profile.email_confirmed:
                    # get mailchimp group_id before the profile change
                    if profile.is_affiliate_account():
                        list_id = settings.MAILCHIMP_LISTS[settings.MAILCHIMP_LIST_AFFILIATORS]
                    else:
                        list_id = settings.MAILCHIMP_LISTS[settings.MAILCHIMP_LIST_USERS]
                    current_group_id = get_mailchimp_group_id(user, list_id, profile)
                    profile.email_confirmed = True
                    profile.save()
                    validlink = True
                    #send welcome email to users that completed setting up their account
                    #otherwise this email will be sent upon completing the account setup process
                    if profile.is_account_setup_completed:
                        senders.send_registration_email(user)
                    #add site notification
                    self.add_email_confirmation_success_notification(user)
                    #track this event
                    mixpanel_track_email_confirmation.apply_async(
                        kwargs={'user_id': user.id}, queue='analytics')

                    #move user to the email confirmed /customers / affiliate_confirmed group
                    new_group_id = get_mailchimp_group_id(user, list_id, profile)
                    group_settings = {
                       current_group_id: False,
                       new_group_id: True
                    }
                    subscribe_user.apply_async(
                        kwargs={
                            'user': user,
                            'list_id': list_id,
                            'group_settings': group_settings
                        },
                        countdown=60 * 2, #wait 2 minutes to avoid errors on mailchimp's end
                        queue='analytics')
        ctx = {'validlink': validlink}
        return self.render_to_response(ctx)

    def add_email_confirmation_success_notification(self, user):
        body_html_tpl = loader.get_template(
            'customer/alerts/site_notifications/email_confirmed.html')
        data = {'no_display': True}
        body = body_html_tpl.render(Context(data))
        subject = _("Your email address has been confirmed")
        Dispatcher().notify_user(user, subject, body, category='Info')


class OrderHistoryView(CoreOrderHistoryView):
    def get_queryset(self):
        """
        Filter out orders that need to be manually authorized
        """
        qs = super(OrderHistoryView, self).get_queryset()
        return qs\
            .select_related('package', 'tracking')\
            .exclude(status__in=['Cancelled', 'Pending'])

class OrderDetailView(CoreOrderDetailView):
    def get_object(self, queryset=None):
        obj = get_object_or_404(self.model, user=self.request.user,
                                 number=self.kwargs['order_number'])
        #don't show cancelled/pending orders
        if obj.status in ['Cancelled', 'Pending']:
            raise Http404
        return obj


class OrderInvoiceView(DetailView):
    model = Order
    template_name = "customer/order/invoice/order_invoice.html"

    def get_object(self, queryset=None):
        return get_object_or_404(self.model, user=self.request.user,
                                 number=self.kwargs['order_number'])

    def get_invoice_filename(self, order):
        return "order%sinvoice.pdf" % order.number

    def get(self, request, *args, **kwargs):
        order = self.get_object()
        template = loader.get_template(self.template_name)
        main_pdf = pisaPDF()
        voucher_codes = []
        for discount in order.discounts.all():
                if discount.voucher_code:
                    voucher_codes.append(discount.voucher_code)

        context = RequestContext(request, {
            'order': order,
            'voucher_codes': voucher_codes,
            'STATIC_ROOT': settings.PROJECT_DIR
        })
        html = template.render(context)
        result = StringIO()

        order_pdf = pisa.pisaDocument(StringIO(html.encode("UTF-8")), result)

        if order_pdf.err:
            messages.error(
                self.request,
                _("Something went wrong while trying to generate the invoice for "
                  "order #%s, please try again soon.") % order.number,
            )
            return HttpResponseRedirect(reverse('customer:order-list'))
        else:
            main_pdf.addDocument(order_pdf)

        return HttpResponse(main_pdf.getvalue(), mimetype='application/pdf')
        #filename = self.get_invoice_filename(order)
        #response['Content-Disposition'] = 'attachment; filename=%s' % filename
        #return response


class TourStartedView(View):
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            end_step = request.POST.get('end_step', 0)
            profile = request.user.get_profile()
            profile.tour_started = True
            profile.tour_end_step = end_step
            profile.save()
        return HttpResponse(status=200)


class FeedbackView(FormView):
    form_class = CustomerFeedbackForm
    template_name = 'customer/feedback/take_feedback.html'
    order = None

    def dispatch(self, request, *args, **kwargs):
        """
            Validate that the order was placed by the logged in user
        """
        self.order = get_object_or_404(Order,
                                       pk=kwargs['pk'],
                                       user=request.user)
        self.customer = request.user
        return super(FeedbackView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        """
        Make sure feedback wasn't submitted for the given order
        """
        try:
            self.order.feedback
        except ObjectDoesNotExist:
            pass
        else:
            messages.error(request,
                           _("We've already received your feedback for order %s, thanks again.")
                           % self.order.number)
            return HttpResponseRedirect(reverse('customer:profile-view'))

        return super(FeedbackView, self).get(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super(FeedbackView, self).get_form_kwargs()
        kwargs['order'] = self.order
        kwargs['customer'] = self.customer
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super(FeedbackView, self).get_context_data(**kwargs)
        ctx['title'] = _("Order %s | Your feedback") % self.order.number
        return ctx

    def form_valid(self, form):
        form.save()
        #give credits for users who shared their order feedback with us
        responses.credit_order_feedback(self.request.user)
        messages.success(self.request,
                         _("Feedback successfully received. <br/> Thank you"
                           " for helping us improving the USendHome experience."),
                         extra_tags='safe')
        return HttpResponseRedirect(reverse('customer:profile-view'))


class AdditionalReceiverCreateView(AjaxTemplateMixin,
                                   AuthenticationDocumentsNotificationMixin,
                                   CreateView):
    form_class = AdditionalPackageReceiverForm
    receiver_document_formset = AdditionalPackageReceiverDocumentFormSet
    model = AdditionalPackageReceiver
    template_name = 'customer/receivers/additional_receiver_add.html'
    ajax_template_name = 'customer/receivers/additional_receiver_add_form.html'
    page_title = _('Add Additional Receiver')

    def get_form_kwargs(self):
        kwargs = super(AdditionalReceiverCreateView, self).get_form_kwargs()
        kwargs['package_owner'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super(AdditionalReceiverCreateView, self).get_context_data(**kwargs)
        if 'receiver_document_formset' not in ctx or not ctx['receiver_document_formset']:
            ctx['receiver_document_formset'] = self.receiver_document_formset()
        ctx['page_title'] = self.page_title
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = None
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        receiver_document_formset = self.receiver_document_formset(
            self.request.POST, self.request.FILES)
        if form.is_valid() and receiver_document_formset.is_valid():
            return self.form_valid(form, receiver_document_formset)
        else:
            return self.form_invalid(form, receiver_document_formset)

    def form_valid(self, form, receiver_document_formset):
        self.object = form.save()
        receiver_document_formset.instance = self.object
        receiver_document_formset.save()
        self.send_admin_notification_email(
            unit=self.request.user.get_profile().uuid,
            subject="Additional package receiver documents")
        return self.json_response(redirect_url=self.get_success_url())

    def form_invalid(self, form, receiver_document_formset):
        ctx = self.get_context_data(form=form,
                                    receiver_document_formset=receiver_document_formset)
        if self.request.is_ajax():
            return self.json_response(ctx=ctx)
        return self.render_to_response(ctx)

    def get_success_url(self):
        messages.success(self.request,
                         _("Additional receiver %s successfully added.<br/>Once we finish reviewing the documents"
                           " you will be able to release packages addressed to this receiver.") %
                         self.object.get_full_name(),
                         extra_tags='safe')
        return reverse('customer:additional-receiver-list')


class AdditionalReceiverVerifyView(AjaxTemplateMixin,
                                   AuthenticationDocumentsNotificationMixin,
                                   CreateView):
    form_class = AdditionalPackageReceiverDocumentFormSet
    model = PackageReceiverDocument
    template_name = 'customer/receivers/additional_receiver_verify.html'
    ajax_template_name = 'customer/receivers/additional_receiver_verify_form.html'
    page_title = _('Additional Receiver Verification')

    def get_context_data(self, **kwargs):
        ctx = super(AdditionalReceiverVerifyView, self).get_context_data(**kwargs)
        ctx['page_title'] = self.page_title
        return ctx

    def dispatch(self, request, *args, **kwargs):
        self.additional_receiver = get_object_or_404(
            AdditionalPackageReceiver, pk=kwargs['pk'], package_owner=request.user)
        #check if verification is needed
        if not self.additional_receiver.authentication_documents_required():
            messages.info(request, _("We've already received documents for this receiver,"
                                     " no need to upload any new documents."))
            return HttpResponseRedirect(reverse('customer:additional-receiver-list'))
        return super(AdditionalReceiverVerifyView, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance = self.additional_receiver
        self.object = form.save()
        #change verification status
        self.additional_receiver.verification_status = AdditionalPackageReceiver.VERIFICATION_IN_PROGRESS
        self.additional_receiver.save()
        self.send_admin_notification_email(
            unit=self.request.user.get_profile().uuid,
            subject="Additional package receiver documents")
        return self.json_response(redirect_url=self.get_success_url())

    def form_invalid(self, form):
        ctx = self.get_context_data(form=form)
        if self.request.is_ajax():
            return self.json_response(ctx=ctx)
        return self.render_to_response(ctx)

    def get_success_url(self):
        messages.success(self.request,
                        _("Documents received, we will review them shortly."))
        return reverse('customer:additional-receiver-list')


class AdditionalReceiverListView(ListView):
    """Customer address book"""
    context_object_name = "additional_receivers"
    template_name = 'customer/receivers/additional_receivers_list.html'
    paginate_by = 40
    page_title = _('Additional Receivers')

    def get_context_data(self, **kwargs):
        ctx = super(AdditionalReceiverListView, self).get_context_data(**kwargs)
        ctx['page_title'] = self.page_title
        return ctx

    def get_queryset(self):
        """Return customer's addresses"""
        return AdditionalPackageReceiver._default_manager.filter(
            package_owner=self.request.user).order_by('-date_created')


class AdditionalReceiverDeleteView(AjaxTemplateMixin, DeleteView):
    model = AdditionalPackageReceiver
    ajax_template_name = "customer/receivers/additional_receiver_delete_inner.html"
    page_title = _('Delete Additional Receiver?')
    context_object_name = 'additional_receiver'

    def get_context_data(self, **kwargs):
        ctx = super(AdditionalReceiverDeleteView, self).get_context_data(**kwargs)
        ctx['pk'] = self.kwargs.get('pk')
        return ctx

    def get_queryset(self):
        return AdditionalPackageReceiver._default_manager.filter(
            package_owner=self.request.user)

    def get_success_url(self):
        messages.success(self.request,
                        _("Additional receiver %s deleted") % self.object.get_full_name().title())
        return reverse('customer:additional-receiver-list')

    def post(self, *args, **kwargs):
        if self.request.is_ajax():
            self.object = self.get_object()
            #check if the additional receiver can be deleted (has no packages under his name or
            # we're reveiwing his documents)
            if self.object.receiver_packages.exists():
                messages.info(self.request, _("Additional receiver with packages under"
                                              " his name can't be deleted."))
                return self.json_response(
                    is_valid=True,
                    redirect_url=reverse('customer:additional-receiver-list'))
            if self.object.verification_status == AdditionalPackageReceiver.VERIFICATION_IN_PROGRESS:
                messages.info(self.request, _("Additional receiver can't be deleted while reviewing process"
                                              " is in progress."))
                return self.json_response(
                    is_valid=True,
                    redirect_url=reverse('customer:additional-receiver-list'))
            #continue with the delete operation
            super(AdditionalReceiverDeleteView, self).post(*args, **kwargs)
            redirect_url = self.request.POST.get('redirect_url', reverse('customer:additional-receiver-list'))
            return self.json_response(
                is_valid=True,
                redirect_url=redirect_url
            )
        return HttpResponseRedirect(self.request.META.get('HTTP_REFERER', reverse('customer:address-list')))


class AccountVerifyView(AjaxTemplateMixin,
                        AuthenticationDocumentsNotificationMixin,
                        CreateView):
    form_class = AccountAuthenticationDocumentFormSet
    model = AccountAuthenticationDocument
    template_name = 'customer/account/account_verify.html'
    ajax_template_name = 'customer/account/account_verify_form.html'
    page_title = _('Account Verification')

    def get_context_data(self, **kwargs):
        ctx = super(AccountVerifyView, self).get_context_data(**kwargs)
        ctx['page_title'] = self.page_title
        return ctx

    def dispatch(self, request, *args, **kwargs):
        self.account_status = get_object_or_404(
            AccountStatus, pk=kwargs['pk'], profile=request.user.get_profile())
        #check if verification is needed
        if not self.account_status.authentication_documents_required():
            messages.info(request, _("We've already received your documents,"
                                     " no need to upload any new documents."))
            return HttpResponseRedirect(reverse('customer:profile-view'))
        return super(AccountVerifyView, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance = self.account_status
        self.object = form.save()
        #change verification status
        self.account_status.verification_status = AccountStatus.VERIFICATION_IN_PROGRESS
        self.account_status.save()
        self.send_admin_notification_email(
            unit=self.request.user.get_profile().uuid,
            subject="Account verification documents")
        return self.json_response(redirect_url=self.get_success_url())

    def form_invalid(self, form):
        ctx = self.get_context_data(form=form)
        if self.request.is_ajax():
            return self.json_response(ctx=ctx)
        return self.render_to_response(ctx)

    def get_success_url(self):
        messages.success(self.request,
                         _("Documents received, we will review them shortly."))
        return reverse('customer:profile-view')

class ReferralIndexView(TemplateView):
    is_affiliate = False

    def dispatch(self, request, *args, **kwargs):
        self.is_affiliate = request.user.get_profile().is_affiliate_account()
        return super(ReferralIndexView, self).dispatch(request, *args, **kwargs)

    def get_template_names(self):
        if self.is_affiliate:
            return ['customer/affiliate/index.html']
        return ['customer/referrals/index.html']

    def get_referral_context_data(self, **kwargs):
        profile = self.request.user.get_profile()
        ctx = {}
        ctx['link_clicked_count'] = self.count_response_action('RESPONDED')
        ctx['link_signed_up_count'] = self.count_response_action('USER_SIGNUP')
        ctx['future_package_delivery_credit'] = ctx['link_signed_up_count'] * \
                                                settings.REFERRAL_PROGRAM_CREDITS['PACKAGE_DELIVERY']
        ctx['total_unredeemed_credit'] = profile.referral_unredeemed_credit()
        ctx['total_redeemed_credit'] = profile.referral_redeemed_credit()
        ctx['referral_link'] = profile.referral_link
        ctx['twitter_referral_share_text'] =  'Shop US brands like a US resident with @USendHome.' \
                                              ' Sign up using my link and receive $5' \
                                              ' for your first delivery: %s' % profile.referral_link
        return ctx

    def get_affiliate_context_data(self, **kwargs):
        profile = self.request.user.get_profile()
        ctx = {}
        ctx['link_clicked_count'] = self.count_response_action('RESPONDED')
        ctx['link_signed_up_count'] = self.count_response_action('USER_SIGNUP')
        ctx['future_package_delivery_credit'] = ctx['link_signed_up_count'] * \
                                                settings.AFFILIATE_PROGRAM_CREDITS['PACKAGE_DELIVERY']
        ctx['total_unredeemed_credit'] = profile.referral_unredeemed_credit()
        ctx['total_redeemed_credit'] = profile.referral_redeemed_credit()
        ctx['affiliate_link'] = profile.affiliate_link
        return ctx

    def get_context_data(self, **kwargs):
        ctx = super(ReferralIndexView, self).get_context_data(**kwargs)
        if self.is_affiliate:
            ctx.update(self.get_affiliate_context_data())
        else:
            ctx.update(self.get_referral_context_data())
        return ctx

    def count_response_action(self, action):
        return ReferralResponse.objects.filter(
            referral__user=self.request.user,
            action=action).count()

class AffiliateRegisterView(RegisterUserMixin, FormView):
    form_class = AffiliateCreationForm
    template_name = 'customer/affiliate/affiliate_registration.html'

    def dispatch(self, request, *args, **kwargs):
        # log out logged in users
        if request.user.is_authenticated():
            if request.user.get_profile().is_affiliate_account():
                return HttpResponseRedirect(reverse('customer:affiliates-index'))
            logout(request)
        return super(AffiliateRegisterView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if operation_suspended():
            return HttpResponseNotFound()
        return super(AffiliateRegisterView, self).post(request, *args, **kwargs)

    def add_welcome_message(self):
        """
        This function shows a messages to newly registered users with
        a button to start the control panel tour
        we show this welcome tour only for non mobile devices
        for mobile we only show a welcome greeting
        """
        messages.info(
            self.request,
            _("<h4><strong>Welcome aboard!</strong></h4>"
              "<p>Your affiliate account has been set up successfully.</p>"
              "<p>You may now post your USendHome affiliate links on your website or blog to start generating"
              " commission for you.</p>"),
            extra_tags='safe noicon')

    def create_referral(self, user):
        """
        Create the affiliate data that includes the private URL
        """
        return Referral.create(
            redirect_to=reverse('promotions:home'),
            user=user,
        )

    def create_affiliate_address(self, user, data):
        """
        Create affiliator address from the registration data
        We save the website address in the notes field to save extra field
        """
        AffiliatorAddress.objects.create(
            user=user,
            first_name=data['first_name'],
            last_name=data['last_name'],
            line1=data['line1'],
            line4=data['city'],
            postcode=data.get('postcode'),
            country=Country.objects.get(pk=data['country']),
            notes=data['website']
        )

    def form_valid(self, form):
        #check for spammers
        check_honeypot(self.request)
        #register and save user
        user_data = {
            'first_name': form.cleaned_data['first_name'],
            'last_name': form.cleaned_data['last_name'],
            'password': form.cleaned_data['password1'],
            'email': form.cleaned_data['email'],
            'username': generate_username(),
        }
        user = self.register_user(user_data)

        #get user location
        user_extra_data = self.get_user_extra_data(self.request)

        #create profile
        profile_kwargs = {
            'uuid': generate_uuid(),
            'user': user,
            'is_account_setup_completed': True,
            'account_type': Profile.AFFILIATE,
            'is_control_panel_modal_shown': True,
            'registration_type': Profile.AFFILIATE,
        }

        if user_extra_data is not None:
            profile_kwargs['city'] = user_extra_data['city']
            profile_kwargs['country'] = user_extra_data['country']
            profile_kwargs['ip'] = user_extra_data['ip']

        #create referral data
        referral = self.create_referral(user)
        profile_kwargs['referral'] = referral
        # save profile
        profile = Profile.objects.create(**profile_kwargs)
        #create affiliate address
        self.create_affiliate_address(user, form.cleaned_data)
        #raise registered signal
        affiliate_registered.send_robust(
            sender=self, user=user, profile=profile,
            mixpanel_anon_id=form.cleaned_data.get('mixpanel_anon_id'))
        senders.add_new_registration_notification(user)
        self.add_welcome_message()
        return HttpResponseRedirect(self.get_success_url())

    def get_success_response(self):
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('customer:affiliates-index')

class LogoutView(CoreLogoutView):
    def get_redirect_url(self, **kwargs):
        return "%s?action=logout" % reverse('promotions:home')
