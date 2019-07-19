from oscar.apps.checkout.views import ShippingMethodView as CoreShippingMethodView
from oscar.apps.checkout.views import ShippingAddressView as CoreShippingAddressView
from oscar.apps.checkout.views import PaymentMethodView as CorePaymentMethodView
from oscar.apps.checkout.views import PaymentDetailsView as CorePaymentDetailsView
from oscar.apps.checkout.views import ThankYouView as CoreThankYouView
from oscar.apps.address.models import Country
from oscar.apps.offer.models import ConditionalOffer
from oscar.apps.basket.forms import BasketVoucherForm
from oscar.apps.basket.signals import voucher_addition
from apps.shipping.repository import Repository
from apps.order.models import Order
from apps.rewards.models import ReferralReward
from apps.shipping.utils import is_eei_required
from apps.catalogue.models import Product, ProductSpecialRequests
from apps.address.models import UserAddress
from oscar.apps.checkout.views import CheckoutSessionMixin
from . import cache
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseBadRequest
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.views.generic import FormView, TemplateView, View
from .forms import ShippingCustomForm, ReturnToStorePrepaidLabelForm, \
    ReturnToStoreShippingAddressForm, ReturnToStoreContentValueForm
from .utils import create_fee_and_add_to_basket
from django.shortcuts import get_object_or_404
from decimal import ROUND_DOWN, Decimal as D
from django.conf import settings
from django.views.generic import RedirectView
from django.utils.translation import ugettext as _
from datetime import datetime, timedelta
from django.template.loader import render_to_string
from django.template import RequestContext
from django.utils import simplejson as json
from oscar.core import ajax
from apps.tasks.utils import ShippingMethodsHandler
from apps.tasks.mixins import CeleryTaskStatusMixin
from apps.address.utils import is_domestic_delivery
from oscar.core.loading import get_class
from django.db.models import get_model
from django.core.exceptions import ObjectDoesNotExist
import logging
#import random

logger = logging.getLogger('checkout')
Applicator = get_class('offer.utils', 'Applicator')
Selector = get_class('partner.strategy', 'Selector')
Voucher = get_model('voucher', 'Voucher')
Basket = get_model('basket', 'Basket')
OrderNote = get_model('order', 'OrderNote')

GENERAL_ERR = _("We're sorry but something went wrong, please try again.")
TWOPLACES = D('0.01')

def none_package_error(request):
    basket = request.basket
    package = basket.get_package()
    logger.critical("Checkout none_package_error function was called,"
                    " package upc = %s, basket id = %s,"
                    " package owner = %s, current user = %s", package.upc if package else 'NONE',
                    basket.id, package.owner if package else 'NONE', request.user.id)
    messages.error(request, GENERAL_ERR)
    return HttpResponseRedirect(reverse('customer:pending-packages'))


class IndexView(CheckoutSessionMixin, RedirectView):
    permanent = False

    def get(self, request, *args, **kwargs):
        """
        Redirect to main control panel page
        """
        url = request.META.get('HTTP_REFERER', reverse('customer:profile-view'))
        return HttpResponseRedirect(url)

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action', '')
        is_return_to_store = action == 'return_to_store'
        package_id = request.POST.get('product_id')
        package = get_object_or_404(Product, id=package_id, owner=request.user)
        checkout_allowed = True
        #check that the user has confirmed email address
        profile = request.user.get_profile()

        if not profile.account_verified():
            err_msg = self.validate_account_status(profile, is_return_to_store)
            if err_msg:
                messages.error(request, err_msg, extra_tags='safe block')
                checkout_allowed = False
        elif not package.receiver_verified():
            err_msg = self.validate_additional_receiver(package, is_return_to_store)
            if err_msg:
                messages.error(request, err_msg, extra_tags='safe block')
                checkout_allowed = False
        elif not profile.email_confirmed:
            messages.error(request, _("You must <a href='%s'>confirm</a> your email address before you can release your"
                                      " packages for delivery.") % reverse('customer:email-confirmation-send'),
                           extra_tags='safe block')
            checkout_allowed = False
        elif package.is_contain_prohibited_items and not is_return_to_store:
            messages.error(request, _("Package contains prohibited items that can't be shipped internationally.<br/>"
                                      "You can only return this package back to the merchant.<br/>"
                                      "Follow through this <a href='%stutorial/#tutorial-q3'>tutorial</a> for"
                                      " a detailed guide." % reverse('faq')),
                           extra_tags='safe')
            checkout_allowed = False

        if checkout_allowed:
            # delete pending orders for the same package
            self.handle_pending_orders(package)
            #link package to basket for further steps ahead
            request.basket.package = package
            #turn on package checkout to skip the empty basket validation
            self.checkout_session.turn_on_package_checkout()
            #reset all return_to_store data
            self.checkout_session.reset_return_to_store()
            #reset shipping data in session
            self.checkout_session.reset_shipping_data()
            if is_return_to_store:
                #turn on return to store checkout
                self.checkout_session.turn_on_return_to_store_checkout()
                #mark that we're dealing with return to merchant checkout
                #this will come handy for the referral program offer where we exclude
                #this offer for return-to-merchant checkouts
                request.basket.type = Basket.RETURN_TO_MERCHANT
            else:
                request.basket.type = Basket.INTERNATIONAL_DELIVERY
            #flush basket to start from fresh basket
            #all fees are being added to basket throughout the checkout process
            request.basket.refresh()
            request.basket.save()
            return self.get_success_response()

        url = request.META.get('HTTP_REFERER', reverse('promotions:home'))
        return HttpResponseRedirect(url)


    def validate_account_status(self, profile, is_return_to_store):
        #return to merchant is always allowed
        if is_return_to_store:
            return None

        if profile.account_verification_in_process():
            return _("You can't release any package for delivery"
                     " while we're reviewing your documents.")
        elif profile.account_verification_required():
            return _("There is a pending verification request on your account.<br/>"
                      "You must <a href='%s'>verify</a> your account before you can release"
                      " your packages for delivery." % reverse('customer:account-verify',
                      kwargs={'pk': profile.account_status.pk}))
        elif profile.account_verification_requires_more_docs():
            return _("We're waiting for additional documents to complete your"
                     " account verification process.")
        else:
            return _("We couldn't verify your account.<br/>"
                     "You can only return your packages back to the merchants.<br/>"
                     "Follow through this <a href='%stutorial/#tutorial-q3'>tutorial</a> for"
                     " a detailed guide." % reverse('faq'))

    def validate_additional_receiver(self, package, is_return_to_store):
        receiver_name = package.additional_receiver.get_full_name()

        #return to merchant is always allowed
        if is_return_to_store:
            return None

        if package.receiver_verification_required():
            return _("%(name)s is not a verified receiver.<br/>Before you can release this package for"
                      " delivery you must <a href='%(verify_url)s'>verify</a> this receiver through"
                      " your control panel." % {
                        'name': receiver_name,
                        'verify_url': reverse('customer:additional-receiver-verify',
                                              kwargs={'pk': package.additional_receiver.pk})})

        elif package.receiver_verification_in_process():
            return _("You can't release this package for delivery while we're reviewing"
                     " the additional receiver's documents.")
        elif package.receiver_verification_requires_more_docs():
            return _("We're waiting for additional documents to complete"
                     " the verification process of %s." % receiver_name)
        else:
            return _("We couldn't verify %s identity.<br/>"
                      "You can only return this package back to the merchant.<br/>"
                      "Follow through this <a href='%stutorial/#tutorial-q3'>tutorial</a>"
                      " for a detailed guide." % (receiver_name, reverse('faq')))

    def handle_pending_orders(self, package):
        pending_orders = Order.objects\
            .filter(package=package, status='Pending')
        if pending_orders.exists():
            messages.warning(self.request, "You have a pending order on this package.<br/>"
                                           "Please contact <a href='mailto:support@usendhome.com?Subject="
                                           "Payment%20completed' target='_top'>support</a> if you've already"
                                           " completed the payment and don't place another order.<br/>"
                                           "Otherwise, you may continue with the order.",
                             extra_tags='safe')


    def get_success_response(self):
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        if self.checkout_session.is_return_to_store_enabled():
            return reverse('checkout:return-to-store-index')
        return reverse('checkout:shipping-address')


class ReturnToStoreIndexView(CheckoutSessionMixin, TemplateView):
    """
    First page of the checkout.  We prompt user to either sign in, or
    to proceed as a guest (where we still collect their email address).
    """
    template_name = 'checkout/return_to_store_gateway.html'
    prepaid_label_form_class = ReturnToStorePrepaidLabelForm
    content_value_form_class = ReturnToStoreContentValueForm
    package = None

    def dispatch(self, request, *args, **kwargs):
        self.package = request.basket.get_package()
        #check that we have a linked package and it belongs to the current user
        if not self.package or self.package.owner.id != request.user.id:
            return none_package_error(request)
        return super(ReturnToStoreIndexView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        #check that we're dealing with return to merchant checkout
        if not self.checkout_session.is_return_to_store_enabled():
            messages.error(request, GENERAL_ERR)
            return HttpResponseRedirect(reverse('customer:pending-packages'))

        # Check that the user's basket is not empty
        if not self.checkout_session.is_package_checkout_enabled() and request.basket.is_empty:
            messages.error(request, GENERAL_ERR)
            return HttpResponseRedirect(reverse('customer:pending-packages'))

        self.checkout_session.turn_off_return_to_store_prepaid_checkout()

        # add message about prepaid return label
        messages.info(request, _("Prepaid label must be provided by the merchant "
                                "as returning the package to other individuals is not supported"),
                                extra_tags='safe')
        return super(ReturnToStoreIndexView, self).get(request, *args, **kwargs)


    def get_prepaid_label_form_kwargs(self, request=None):
        kwargs = {}
        if request and request.method == 'POST':
            kwargs.update({
                'data': request.POST,
                'files': request.FILES,
            })
        return kwargs

    def get_content_value_form_kwargs(self, request=None):
        kwargs =  {'initial': {'total_value': self.checkout_session.return_to_store_content_value()}}
        if request and request.method == 'POST':
            kwargs.update({
                'data': request.POST,
                'files': request.FILES,
            })
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super(ReturnToStoreIndexView, self).get_context_data(**kwargs)
        ctx.update(kwargs)

        if 'prepaid_label_form' not in kwargs:
            ctx['prepaid_label_form'] = self.prepaid_label_form_class(**self.get_prepaid_label_form_kwargs())

        if 'content_value_form' not in kwargs:
            ctx['content_value_form'] = self.content_value_form_class(**self.get_content_value_form_kwargs())

        return ctx

    def post(self, request, *args, **kwargs):
        # Use the name of the submit button to determine which form to validate
        if u'prepaid_label_submit' in request.POST:
            return self.validate_prepaid_label_form()
        elif u'content_value_submit' in request.POST:
            return self.validate_content_value_form()
        return self.get(request)

    def json_response(self, flash_messages, **kwargs):
        payload = {'messages': flash_messages.to_json()}
        payload.update(kwargs)
        return HttpResponse(json.dumps(payload),
                            mimetype="application/json")

    def validate_prepaid_label_form(self):
        flash_messages = ajax.FlashMessages()
        form = self.prepaid_label_form_class(**self.get_prepaid_label_form_kwargs(self.request))
        if form.is_valid():
            shipping_label = form.save()
            #save shipping label in sessions so we could fetch it once
            #order is completed to link the order
            self.checkout_session.set_shipping_label_id(shipping_label.pk)
            #mark prepaid label checkout
            self.checkout_session.turn_on_return_to_store_prepaid_checkout()
            #remove contents value from session
            self.checkout_session.del_return_to_store_content_value()
            flash_messages.success(_("Prepaid return label was successfully uploaded."))
            return self.json_response(flash_messages, is_valid=True)

        #collect error messages
        try:
            for error in form.errors['__all__']:
                flash_messages.error(error)
        except KeyError:
            flash_messages.error(_("Something went wrong, please try again later."))
        return self.json_response(flash_messages, is_valid=False)

    def reset_shipping_repository(self):
        #reset shipping repository since the content value may change
        #and we need to recalculate the shipping insurance cost
        key = "%s_return-to-store" % self.package.upc
        self.checkout_session.reset_shipping_repository(key)

    def validate_content_value_form(self):
        form = self.content_value_form_class(self.request.POST)
        if form.is_valid():
            #reset shipping repository since new contents value has been entered
            self.reset_shipping_repository()
            value = form.cleaned_data.get('total_value', 0.0)
            #save package total value in sessions
            self.checkout_session.set_return_to_store_content_value(value)
            #mark that this is a regular return to store checkout
            self.checkout_session.turn_off_return_to_store_prepaid_checkout()
            return HttpResponseRedirect(reverse('checkout:return-to-store-shipping-address'))

        ctx = self.get_context_data(content_value_form=form)
        return self.render_to_response(ctx)

#class BasketIndexView(CheckoutSessionMixin, RedirectView):
#    def get(self, request, *args, **kwargs):
#        package = self.request.basket.get_package()
#        if not package:
#            return none_package_error(request)
#        #check that checkout process is allowed
#        if not package.is_ready_for_checkout():
#            messages.error(request, _("Package is not ready for checkout"))
#            return HttpResponseRedirect(reverse('customer:pending-packages'))
#        #save the code for the chosen shipping method in the sessions
#        method_code = package.shipping_method_code
#        self.checkout_session.use_shipping_method(method_code)
#        #save customs form data in session if we're not dealing with domestic shipment
#        if not self.checkout_session.is_return_to_store_enabled():
#            customs_form_data = package.customs_form_data()
#            self.checkout_session.store_customs_form_fields(key=package.upc, custom_fields=customs_form_data)
#        return super(BasketIndexView, self).get(request, *args, **kwargs)
#
#    def get_redirect_url(self, **kwargs):
#        return reverse('checkout:payment-method')
#


class ReturnToStoreShippingAddressView(CoreShippingAddressView):
    template_name = 'checkout/return_to_store_shipping_address.html'
    form_class = ReturnToStoreShippingAddressForm

    def dispatch(self, request, *args, **kwargs):
        self.package = request.basket.get_package()
        #check that we have a linked package and it belongs to the current user
        if not self.package or self.package.owner.id != request.user.id:
            return none_package_error(request)
        return super(ReturnToStoreShippingAddressView, self).dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super(ReturnToStoreShippingAddressView, self).get_form_kwargs()
        kwargs['merchant_name'] = self.package.title
        return_address = self.package.title + ' RETURN ADDRESS'
        kwargs['initial'] = {'first_name': return_address}
        return kwargs

    def process_battery_status_request(self, status):
        #simple sanity test
        if status not in [self.package.NO_BATTERY, self.package.INSTALLED_BATTERY, self.package.LOOSE_BATTERY]:
            return False
        self.package.battery_status = status
        self.package.save()
        return True

    def get(self, request, *args, **kwargs):
        #check that we're dealing with return to merchant checkout
        if not self.checkout_session.is_return_to_store_enabled():
            messages.error(request, GENERAL_ERR)
            return HttpResponseRedirect(reverse('customer:pending-packages'))

        # Check that the user's basket is not empty
        if not self.checkout_session.is_package_checkout_enabled() and request.basket.is_empty:
            messages.error(request, GENERAL_ERR)
            return HttpResponseRedirect(reverse('customer:pending-packages'))


        #add message about prohibited items
        messages.info(request, _("Please note that USendHome can't send back a package that contains alcoholic beverages"
                                 " back to the merchant."
                                 " If your package contains alcoholic beverages you must contact the seller and ask"
                                 " for prepaid return label."
                                 " Once you have it, head back to the checkout process and upload the prepaid label.<br/>"),
                      extra_tags='safe')
        return super(CoreShippingAddressView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # Check if a shipping address was selected directly (eg no form was
        # filled in)
        request_type = request.POST.get('request_type', 'return_address')
         # continue with the form submit
        if request_type == 'return_address':
            if self.request.user.is_authenticated() \
                    and 'address_id' in self.request.POST:
                address = UserAddress._default_manager.get(
                    pk=self.request.POST['address_id'], user=self.request.user)
                action = self.request.POST.get('action', None)
                if action == 'ship_to':
                    #reset shipping repository since the shipping address may changed
                    self.reset_shipping_repository()
                    # User has selected a previous address to ship to
                    self.checkout_session.ship_to_user_address(address)
                    return HttpResponseRedirect(self.get_success_url())
                else:
                    return HttpResponseBadRequest()
            else:
                #reset shipping repository since the shipping address may changed
                self.reset_shipping_repository()
                return super(CoreShippingAddressView, self).post(
                    request, *args, **kwargs)
        # need to save battery status
        battery_status = request.POST.get('status', '')
        if self.process_battery_status_request(battery_status):
            return HttpResponse('SUCCESS')
        return HttpResponse('FAILURE')

    def get_available_addresses(self):
        return self.request.user.addresses.exclude(
            is_merchant=False).order_by(
            '-is_default_for_shipping', '-num_orders')

    def get_context_data(self, **kwargs):
        ctx = super(ReturnToStoreShippingAddressView, self).get_context_data(**kwargs)
        ctx['title'] = _("Where do you want to send back your package?")
        ctx['form_action'] = reverse('checkout:return-to-store-shipping-address')
        ctx['is_lithium_battery_exists'] = self.package.is_contain_lithium_battery
        return ctx

    def get_initial(self):
        """
        Check that the shipping address in session is merchant address
        """
        initial = super(ReturnToStoreShippingAddressView, self).get_initial()
        if initial:
            if self.checkout_session.is_merchant_address():
                return initial
            return None
        return initial

    def reset_shipping_repository(self):
        #reset shipping repository since the content value may change
        #and we need to recalculate the shipping insurance cost
        key = "%s_return-to-store" % self.package.upc
        self.checkout_session.reset_shipping_repository(key)

    def form_valid(self, form):
        #reset shipping repository since new shipping address was entered
        self.reset_shipping_repository()
        #mark that the shipping address is merchant
        self.checkout_session.shipping_address_type(is_merchant=True)
        #Mark shipping address destination type: domestic
        self.checkout_session.shipping_address_dst_type(is_domestic=True)
        return super(ReturnToStoreShippingAddressView, self).form_valid(form)


class ShippingAddressView(CoreShippingAddressView):
    def dispatch(self, request, *args, **kwargs):
        self.package = request.basket.get_package()
        #check that we have a linked package and it belongs to the current user
        if not self.package or self.package.owner.id != request.user.id:
            return none_package_error(request)
        return super(ShippingAddressView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        #check that we're dealing with return to merchant checkout
        if self.checkout_session.is_return_to_store_enabled():
            messages.error(request, GENERAL_ERR)
            return HttpResponseRedirect(reverse('customer:pending-packages'))

        # Check that the user's basket is not empty
        if not self.checkout_session.is_package_checkout_enabled() and request.basket.is_empty:
            messages.error(request, GENERAL_ERR)
            return HttpResponseRedirect(reverse('customer:pending-packages'))

        #always start with international delivery
        self.checkout_session.shipping_address_dst_type(is_domestic=False)

        #add message about prohibited items
        messages.info(request, _("Make sure your package doesn't contain any restricted item that"
                                 " can't be shipped internationally.<br/>"
                                 "Check out the full list of restricted items <a href='%s#shipping-q8'>here</a>.<br/>"
                                 "<strong>Package that contains prohibited item must be returned back to the merchant</strong>"
                                 % reverse('faq', kwargs={'active_tab': 'shipping'})),
                      extra_tags='safe')

        return super(CoreShippingAddressView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        # Check if a shipping address was selected directly (eg no form was
        # filled in)
        if self.request.user.is_authenticated() \
                and 'address_id' in self.request.POST:
            address = UserAddress._default_manager.get(
              pk=self.request.POST['address_id'], user=self.request.user)
            action = self.request.POST.get('action', None)
            if action == 'ship_to':
                #we would like to get new shipping rates prior to setting new shipping address
                self.reset_shipping_repository()
                # User has selected a previous address to ship to
                self.checkout_session.ship_to_user_address(address)
                return HttpResponseRedirect(self.get_success_url())
            else:
                return HttpResponseBadRequest()
        else:
            #reset shipping repository since the shipping address may changed
            self.reset_shipping_repository()
            return super(ShippingAddressView, self).post(
                request, *args, **kwargs)


    def get_context_data(self, **kwargs):
        ctx = super(ShippingAddressView, self).get_context_data(**kwargs)
        ctx['title'] = _("Where do you want to ship your package?")
        ctx['form_action'] = reverse('checkout:shipping-address')
        return ctx

    def get_initial(self):
        """
        Check that the shipping address in session is not merchant address
        """
        initial = super(ShippingAddressView, self).get_initial()
        if initial:
            if not self.checkout_session.is_merchant_address():
                if 'country_id' in initial:
                    country_id = initial['country_id']
                    #need to align country field since we store the country_id in session
                    country = Country.objects.get(iso_3166_1_a2=country_id)
                    del initial['country_id']
                    initial['country'] = country
                    return initial
            return None
        return initial

    def reset_shipping_repository(self):
        key = self.package.upc
        self.checkout_session.reset_shipping_repository(key)

    def get_form_kwargs(self):
        profile = self.request.user.get_profile()
        kwargs = super(ShippingAddressView, self).get_form_kwargs()
        kwargs['is_business_account'] = profile.is_business_account()
        return kwargs

    def form_valid(self, form):
        #we would like to get new shipping rates prior to setting new shipping address
        self.reset_shipping_repository()
        #mark that the shipping address is not merchant
        self.checkout_session.shipping_address_type(is_merchant=False)
        #Mark shipping address destination type: domestic or international
        self.checkout_session.shipping_address_dst_type(
            is_domestic=is_domestic_delivery(form.cleaned_data['country'].iso_3166_1_a2))
        return super(ShippingAddressView, self).form_valid(form)


    def get_available_addresses(self):
        return self.request.user.addresses\
            .exclude(is_merchant=True)\
            .order_by('-is_default_for_shipping', '-num_orders')

    def get_success_url(self):
        return reverse('checkout:customs')


class CustomView(CheckoutSessionMixin, FormView):
    """
    We prompt user to enter package content information for custom and for shipping invoice
    """
    template_name = 'checkout/custom.html'
    form_class = ShippingCustomForm
    num_of_items = 50
    package = None

    def dispatch(self, request, *args, **kwargs):
        self.package = request.basket.get_package()
        #check that we have a linked package and it belongs to the current user
        if not self.package or self.package.owner.id != request.user.id:
            return none_package_error(request)
        return super(CustomView, self).dispatch(request, *args, **kwargs)


    def get(self, request, *args, **kwargs):
        #check that we're dealing with return to merchant checkout
        if self.checkout_session.is_return_to_store_enabled():
            messages.error(request, GENERAL_ERR)
            return HttpResponseRedirect(reverse('customer:pending-packages'))

        # Check that the user's basket is not empty
        if not self.checkout_session.is_package_checkout_enabled() and request.basket.is_empty:
            messages.error(request, GENERAL_ERR)
            return HttpResponseRedirect(reverse('customer:pending-packages'))

        # Check that shipping address has been completed
        if not self.checkout_session.is_shipping_address_set():
            messages.error(request, _("Please choose a shipping address."))
            return HttpResponseRedirect(reverse('checkout:shipping-address'))

        # Notify customer that he needs to fill in the missing item value data
        if self.missing_item_value():
            messages.info(request, _("The customs declaration could not be completed due to missing order receipt.<br/>"
                                     "Please fill the missing information in the highlighted fields below."), extra_tags='safe')
        else:
            #add message with customs tutorial
            messages.info(request, _("Don't know how to properly declare the goods?<br/>"
                                     "Follow along with this detailed <a href='%s#tutorial-q9' target='_blank'>tutorial</a>"
                                     " to get this form filled in no time."
                                     % reverse('faq', kwargs={'active_tab': 'tutorials'})),
                          extra_tags='safe')

        return super(CustomView, self).get(request, *args, **kwargs)

    def customs_paperwork_completed_by_us(self):
        try:
            special_requests = self.package.special_requests
        except ProductSpecialRequests.DoesNotExist:
            return False
        else:
            return special_requests.filling_customs_declaration_done

    def missing_item_value(self):
        try:
            return self.package.customs_form.missing_item_value_exists()
        except ObjectDoesNotExist:
            return False

    def is_all_form_fields_readonly(self):
        """
        We need to grey out all customs form declaration fields in case
        the customer has asked us to fill the customs form declaration for him
        There's 1 exception where we couldn't tell the values of all items, in such case
        we let the user to fill in the missing data.
        """
        return self.customs_paperwork_completed_by_us() #and not self.missing_item_value()
        #return False

    def reset_shipping_repository(self):
        key = self.package.upc
        self.checkout_session.reset_shipping_repository(key)

    def get_form_kwargs(self):
        kwargs = super(CustomView, self).get_form_kwargs()
        kwargs['package'] = self.package
        kwargs['num_of_items'] = self.num_of_items
        kwargs['is_readonly'] = self.is_all_form_fields_readonly()
        kwargs['missing_value'] = self.missing_item_value()
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super(CustomView, self).get_context_data(**kwargs)
        ctx['is_domestic_shipment'] = self.checkout_session.is_domestic_address()
        ctx['is_lithium_battery_exists'] = self.package.is_contain_lithium_battery
        return ctx

    def get_initial(self):
        """
        Populate the custom form declaration with previous data (if any)
        """
        #first check in session
        customs_form_data = self.checkout_session.new_customs_form_fields(self.package.upc)
        if not customs_form_data:
            #fallback to db
            customs_form_data = self.package.customs_form_data()

        return customs_form_data

    def process_battery_status_request(self, status):
        #simple sanity test
        if status not in [self.package.NO_BATTERY, self.package.INSTALLED_BATTERY, self.package.LOOSE_BATTERY]:
            return False
        self.package.battery_status = status
        self.package.save()
        return True

    def post(self, request, *args, **kwargs):
        request_type = request.POST.get('request_type', 'customs_declaration')
        # continue with the form submit
        if request_type == 'customs_declaration':
            return super(CustomView, self).post(request, *args, **kwargs)
        # need to save battery status
        battery_status = request.POST.get('status', '')
        if self.process_battery_status_request(battery_status):
            return HttpResponse('SUCCESS')
        return HttpResponse('FAILURE')

    def form_valid(self, form):
        #save object to db
        obj = form.save()
        #need to clear shipping repository on every customs form submit
        #since some shipping methods rely on the contents type attribute
        self.reset_shipping_repository()
        form_data = form.cleaned_data if obj else self.package.customs_form_data()
        #save custom form in session
        key = self.package.upc
        self.checkout_session.store_customs_form_fields(key, form_data)
        return super(CustomView, self).form_valid(form)

    def get_success_url(self):
        # loose batteries can't be shipped from the USA, need to redirect back
        # to pending packages page with an proper message
        domestic_delivery = self.checkout_session.is_domestic_address()
        if not domestic_delivery and self.package.battery_status ==  self.package.LOOSE_BATTERY:
            messages.error(self.request, _("Due to regulations by the IATA, FAA and the TSA, "
                                           "USendHome no longer will be able to ship loose Lithium Ion batteries<br>"
                                           "(PI965) for our customers. Package must be returned back to the merchant."),
                           extra_tags='safe block')
            return reverse('customer:pending-packages')
        return reverse('checkout:shipping-method')


class ShippingMethodView(CoreShippingMethodView, ShippingMethodsHandler, CeleryTaskStatusMixin):
    shipping_methods_template_name = "checkout/partials/shipping_methods_result_checkout.html"

    def collect_country_related_messages(self, msgs):
        shipping_address = self.get_shipping_address(self.request.basket)
        to_country_code = shipping_address.country.iso_3166_1_a2
        try:
            country_msgs = settings.COUNTRY_RELATED_MESSAGES[to_country_code]
            msgs[messages.WARNING].extend(country_msgs)
            return True
        except Exception:
            return False

    def collect_messages(self, msgs, package, flash_messages):
        domestic_delivery = self.checkout_session.is_domestic_address()
        if not domestic_delivery:
            msgs[messages.INFO].append(_("International shipping rates don't include customs duties, taxes or any other fee"
                                     " besides postage.<br>USendHome has no control over those charges and they"
                                     " are the sole responsibility of the customer."))
        country_related_msg_collected = self.collect_country_related_messages(msgs)
        if not country_related_msg_collected:
            if package.is_contain_lithium_battery:
                if domestic_delivery:
                    if package.battery_status != package.NO_BATTERY:
                        msgs[messages.WARNING].append(_("Package contains lithium batteries that can only be shipped"
                                                    " via USPS ground services."))
                else:
                    if package.battery_status == package.INSTALLED_BATTERY:
                        msgs[messages.WARNING].append(_("Package contains installed lithium battery that can only be shipped"
                                                        " via express carriers (not USPS)."))
        #collect all messages
        self.add_flash_messages(flash_messages, msgs)
        total_value = self.get_total_value(package)
        self.add_insurance_message(total_value, flash_messages)

    def handle_celery_task_result(self, result):
        repo = Repository()
        basket = self.request.basket
        shipping_methods = result.pop('methods', [])
        flash_messages = ajax.FlashMessages()
        msgs = result.pop('flash_messages', {})
        package = basket.get_package()

        #align black friday rates if user is qualified for such discount
        try:
            black_friday_shipping_offer = ConditionalOffer\
                .objects.get(name='Black Friday Shipping Discount')
        except ConditionalOffer.DoesNotExist:
            pass
        else:
            if black_friday_shipping_offer.is_available() and\
               black_friday_shipping_offer.is_condition_satisfied(self.request.basket):
                for method in shipping_methods:
                    base_rate = method.ship_charge_excl_revenue
                    #we take a flat fee of $5
                    new_rate = (base_rate + D('5.0')) * D('1.25')
                    method.ship_charge_incl_revenue = new_rate
                    method.ship_charge_incl_revenue.quantize(TWOPLACES, rounding=ROUND_DOWN)

        if shipping_methods:
            key = package.upc
            if self.checkout_session.is_return_to_store_enabled():
                key += "_return-to-store"

            repo.set_methods(shipping_methods)
            repo.prime_methods(basket, shipping_methods)
            self.checkout_session.store_shipping_repository(key, repo)

            self.collect_messages(msgs, package, flash_messages)
        else:
            flash_messages.info(_("No matching shipping methods found, click "
                      "<a href='mailto:support@usendhome.com?Subject=Checkout%20error' target='_top'>here</a>"
                      " to email customer support.<br><a href='/'>Return back to site</a>."))

        return self.shipping_methods_json_response(
            request=self.request,
            ctx={'methods': shipping_methods},
            flash_messages=flash_messages,
            html_template=self.shipping_methods_template_name,
            status='COMPLETED',
            new_results=True)

    def get_shipping_methods(self, package, total_value):
        #since insurance is calculated based on content value that may change
        #we need to align it to match current value
        basket = self.request.basket
        #no shipping methods available need to launch a background task to calculate them
        repo = Repository()
        #get package total value if the customer returns the package back to store
        #since we don't get total value from customs form because one does not required
        #for domestic shipments
        shipping_address = self.get_shipping_address(basket)
        task = repo.get_shipping_methods(
                user=self.request.user,
                basket=self.request.basket,
                total_value=total_value,
                shipping_addr=shipping_address,
                package=package)

        return self.shipping_methods_json_response(
            request=self.request,
            ctx=None,
            flash_messages=None,
            task_id=task.id,
            new_results=True,
            status='RUNNING')

    def get_available_shipping_methods(self, package=None):
        """
        Returns all applicable shipping method objects
        for a given basket.
        """
        basket = self.request.basket
        # try to fetch the shipping methods from cache
        key = package.upc
        if self.checkout_session.is_return_to_store_enabled():
            key += "_return-to-store"
        return self.checkout_session.available_shipping_methods(key, basket=basket)


    def is_flash_messages_exist(self, flash_msgs):
        return (flash_msgs and (len(flash_msgs[messages.ERROR]) or len(flash_msgs[messages.INFO])))

    def add_insurance_message(self, total_value, flash_messages):
        #add insurance promo message
        if total_value > 100:
            flash_messages.info("We highly recommend you insure any shipment valued at more"
                                " than $100 for maximum protection.")

    def get_total_value(self, package):
        #get total value of the package
        if self.checkout_session.is_return_to_store_enabled():
            total_value = self.checkout_session.return_to_store_content_value()
        else:
            total_value = package.total_content_value()
        return total_value

    def get(self, request, *args, **kwargs):
        #need to run the background task to fetch shipping methods
        if request.is_ajax():
            task_id = request.GET.get('task_id')
            if task_id:
                return self.task_status(task_id)
            ctx = {}
            msgs = {messages.ERROR: [], messages.INFO: [], messages.WARNING: []}
            flash_messages = ajax.FlashMessages()

            # Check that the user's basket is not empty
            if not self.checkout_session.is_package_checkout_enabled() and request.basket.is_empty:
                messages.error(request, GENERAL_ERR)
                redirect = reverse('customer:pending-packages')
                return self.json_response(ctx=None, flash_messages=flash_messages, redirect=redirect)

            # Check that shipping address has been completed
            if not self.checkout_session.is_shipping_address_set():
                messages.error(request, _("Please choose a shipping address."))
                redirect = reverse('checkout:shipping-address')
                return self.json_response(ctx=None, flash_messages=flash_messages, redirect=redirect)

            package = request.basket.get_package()
            if not package:
                logger.error("Package product data could not be fetched from cache")
                messages.error(request, GENERAL_ERR)
                redirect = reverse('customer:pending-packages')
                return self.json_response(ctx=None, flash_messages=flash_messages, redirect=redirect)

            # Check that custom form has been completed
            if not self.checkout_session.is_customs_form_set(key=package.upc) and \
               not self.checkout_session.is_return_to_store_enabled():
                messages.error(self.request, _("Please fill out the customs declaration form."))
                redirect = reverse('checkout:customs')
                return self.json_response(ctx=None, flash_messages=flash_messages, redirect=redirect)

            total_value = self.get_total_value(package)

            # Save shipping methods as instance var as we need them both here
            # and when setting the context vars.
            self._methods = self.get_available_shipping_methods(package)
            if self._methods is None:
                return self.get_shipping_methods(package, total_value)
            ctx.update({'methods': self._methods})
            if not self._methods:
                flash_messages.info(_("No matching shipping methods found, click "
                          "<a href='mailto:support@usendhome.com?Subject=Checkout%20error' target='_top'>here</a>"
                          " to email customer support.<br><a href='/'>Return back to site</a>."))
            else:
                self.collect_messages(msgs, package, flash_messages)
            return self.shipping_methods_json_response(
                request,
                ctx,
                flash_messages=flash_messages,
                html_template=self.shipping_methods_template_name,
                new_results=False)

        context = super(CoreShippingMethodView, self).get_context_data(**kwargs)
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        """
        This function is called after user selected shipping method
        this is what we do here:
        1 - save selected shipping method
        2 - create new product which holds the shipping costs
        3 - add the new product to basket
        """
        # Need to check that this code is valid for this user
        method_code = request.POST.get('method_code', '')
        insurance_needed = request.POST.get('insurance', 'no')

        is_valid = False

        package = request.basket.get_package()
        #check that we have a linked package and it belongs to the current user
        if not package or package.owner.id != request.user.id:
            return none_package_error(request)

        methods = self.get_available_shipping_methods(package)
        #fetch methods once again
        if not methods:
            return HttpResponseRedirect(reverse('checkout:shipping-method'))

        for method in methods:
            if method.code == method_code:
                is_valid = True

        if not is_valid:
            messages.error(request, _("Your selected shipping method is not applicable, please pick another one."))
            return HttpResponseRedirect(reverse('checkout:shipping-method'))

        # Save the code for the chosen shipping method in the sessions
        self.checkout_session.use_shipping_method(method_code)

        #add products to basket:
        #shipping method, bank fee, forwarding fee and insurance fee (if needed)
        #and continue to the next step.
        key = package.upc
        #make special key for return to store checkout where we need to
        #show only domestic methods
        if self.checkout_session.is_return_to_store_enabled():
            key += "_return-to-store"
        repo = self.checkout_session.get_shipping_repository(key)

        #we should never get here - but if we do show error message and redirect to account summary
        if not repo:
            logger.error("We could not fetch shipping repository from cache")
            messages.error(request, GENERAL_ERR)
            return HttpResponseRedirect(reverse('customer:pending-packages'))

        #add shipping option to basket
        shipping_method = repo.get_shipping_method_by_code(method_code)
        shipping_cost = shipping_method.shipping_method_cost()
        method_name_with_carrier = "%(carrier)s %(method_name)s" % {
            'carrier': shipping_method.display_carrier,
            'method_name': shipping_method.name
        }
        create_fee_and_add_to_basket(
            title=method_name_with_carrier,
            charge=shipping_cost,
            package=package,
            basket=request.basket,
            prefix=settings.SHIPPING_RATES_TEMPLATE,
            position=settings.SHIPPING_FEE_POSITION,
            product_class_name='shipping method',
            category='shipping_method'
        )
        #add insurance to basket (if needed)
        if insurance_needed == 'yes':
            #add the fee if and only if we charge for the insurance
            #express carriers offer free insurance when contents value < $100
            if not shipping_method.free_insurance:
                create_fee_and_add_to_basket(
                    title=_('Shipping Insurance'),
                    charge=shipping_method.shipping_insurance_cost(),
                    package=package,
                    basket=request.basket,
                    prefix=settings.SHIPPING_INSURANCE_TEMPLATE,
                    position=settings.INSURANCE_FEE_POSITION,
                    category='shipping_insurance',
                    cost_price=shipping_method.ins_charge_excl_revenue)
        #remove the line that holds the insurance charge product since user can select shipping
        #method that does not have insurance
        else:
            #remove from basket and db
            upc = settings.SHIPPING_INSURANCE_TEMPLATE % package.upc
            try:
                insurance_fee_product = package.variants.get(upc=upc)
            except Product.DoesNotExist:
                pass
            else:
                request.basket.remove_product_line(insurance_fee_product)
                insurance_fee_product.delete()

        #add bank fee
        # (4.5% of shipping cost)'
        bank_fee = D(getattr(settings, 'BANK_FEE', '0.045'))
        charge = shipping_cost * bank_fee
        create_fee_and_add_to_basket(
            title=_('Payment Processing'),
            charge=charge,
            package=package,
            basket=request.basket,
            prefix=settings.PAYMENT_PROCESSING_TEMPLATE,
            position=settings.BANK_FEE_POSITION)

        #save carrier and display_carrier in cache for the creation of OrderTracking model
        key = "%s_%s" % (package.upc, 'carrier')
        cache.store_order_tracking_value(key, shipping_method.carrier)
        key = "%s_%s" % (package.upc, 'display_carrier')
        cache.store_order_tracking_value(key, shipping_method.display_carrier)

        return self.get_success_response()

    def json_response(self, ctx, flash_messages, **kwargs):
        payload = {'messages': flash_messages.to_json()}
        payload.update(kwargs)
        if ctx is not None:
            content_html = render_to_string(
                'shipping/shipping_methods_search_results.html',
                RequestContext(self.request, ctx))
            payload.update({'content_html': content_html})
        return HttpResponse(json.dumps(payload),
                            mimetype="application/json")


class PaymentMethodView(CorePaymentMethodView):
    template_name = 'checkout/payment_method.html'
    FIXED_FEES_POSITIONS = {
        'missing_client_id': settings.MISSING_CLIENT_ID_FEE_POSITION,
        'over_weight': settings.OVER_WEIGHT_FEE_POSITION,
        'custom_fee': settings.CUSTOM_FEE_POSITION,
    }

    def get_context_data(self, **kwargs):
        context = super(PaymentMethodView, self).get_context_data(**kwargs)
        context['voucher_form'] = BasketVoucherForm()
        context['use_bitcoinpay'] = True #random.random() > 0.5
        context['is_return'] = self.checkout_session.is_return_to_store_enabled()
        return context

    def add_special_request_fees(self, package, is_child=False, position=None):
        #get special requests fees
        special_requests_fees = package.variants.filter(status="special_requests")
        count = 0
        for special_requests_fee in special_requests_fees:
            #add fee to basket
            ret = self.request.basket.add_product_if_not_exists(
                product=special_requests_fee,
                position=settings.SPECIAL_REQUESTS_FEE_POSITION if not is_child else position + count,
            )
            if ret == 'ADDED':
                count += 1
                if is_child:
                    #update fee title (only once)
                    if 'of package' not in special_requests_fee.title:
                        special_requests_fee.title += _(' of package #%s' % package.upc)
                        special_requests_fee.save()
        return count

    def add_fixed_fees(self, package, is_child=False, position=None):
        fixed_fees = package.variants.filter(status='fixed_fees')
        count = 0
        for fixed_fee in fixed_fees:
            #add fee to basket
            key = fixed_fee.upc.rsplit("_", 1)[0]
            try:
                fixed_fee_position = self.FIXED_FEES_POSITIONS[key]
            except KeyError:
                fixed_fee_position = settings.LAST_FEE_POSITION
            ret = self.request.basket.add_product_if_not_exists(
                product=fixed_fee,
                position=fixed_fee_position if not is_child else position + count
            )
            if ret == 'ADDED':
                count += 1
                if is_child:
                    #update fee title (only once)
                    if 'of package' not in fixed_fee.title:
                        fixed_fee.title += _(' of package #%s' % package.upc)
                        fixed_fee.save()
        return count

    def _calculate_package_extra_storage_days(self, package, valid_time):
        days = 0
        date_created = package.date_created
        #get only year month and day
        date_created = date_created.replace(hour=0, minute=0, second=0, microsecond=0)

        if valid_time > date_created:
            delta = valid_time - date_created
            days += delta.days

        return days

    def _calculate_post_consolidation_extra_days(self, package, valid_time):
        days = 0
        date_consolidated = package.date_consolidated
        #we need to support backward compatibility
        #for all consolidated packages that don't have the consolidation date
        if date_consolidated:
            #get only year month and day
            date_consolidated = date_consolidated.replace(hour=0, minute=0, second=0, microsecond=0)
            if valid_time > date_consolidated:
                delta = valid_time - date_consolidated
                days += delta.days
        return days

    def get_extra_storage_days(self, package):
        """
        return the extra storage days for the package
        based on FREE_STORAGE_IN_DAYS
        """
        now = datetime.now()
        #get only year month and day
        now = now.replace(hour=0, minute=0, second=0, microsecond=0)
        #consolidated packages have 30 days free of storage while other packages have 10 days
        if package.is_consolidated:
            max_allowed_days = getattr(settings, 'CONSOLIDATED_FREE_STORAGE_IN_DAYS', 30)
        else:
            max_allowed_days = getattr(settings, 'FREE_STORAGE_IN_DAYS', 10)
        valid_time = now - timedelta(days=max_allowed_days)
        return self._calculate_package_extra_storage_days(package, valid_time)

    def get_post_consolidation_days(self, package):
        now = datetime.now()
        #get only year month and day
        now = now.replace(hour=0, minute=0, second=0, microsecond=0)
        max_allowed_days = getattr(settings, 'FREE_POST_CONSOLIDATION_IN_DAYS', 3)
        valid_time = now - timedelta(days=max_allowed_days)
        return self._calculate_post_consolidation_extra_days(package, valid_time)


    def add_extra_storage_fee(self, package):
        """
        We need to handle a special case for consolidated packages
        where storage fee is applied for consolidated packages that wait for more
        than 3 days in storage
        """
        #check for storage fee
        extra_storage_days = self.get_extra_storage_days(package)
        cost_per_day = D(getattr(settings, 'EXTRA_STORAGE_FEE', '1.0'))

        if not package.is_consolidated:
            #add storage fee to basket
            if extra_storage_days > 0:
                create_fee_and_add_to_basket(
                    title=_('Storage Surcharge'),
                    charge=cost_per_day,
                    package=package,
                    basket=self.request.basket,
                    prefix=settings.EXTRA_STORAGE_TEMPLATE,
                    position=settings.EXTRA_STORAGE_FEE_POSITION,
                    quantity=extra_storage_days)
        else:
            post_consolidation_days = self.get_post_consolidation_days(package)
            if extra_storage_days > post_consolidation_days:
                create_fee_and_add_to_basket(
                    title=_('Storage Surcharge'),
                    charge=cost_per_day,
                    package=package,
                    basket=self.request.basket,
                    prefix=settings.EXTRA_STORAGE_TEMPLATE,
                    position=settings.EXTRA_STORAGE_FEE_POSITION,
                    quantity=extra_storage_days)
            elif post_consolidation_days > 0:
                create_fee_and_add_to_basket(
                    title=_('Storage Surcharge'),
                    charge=cost_per_day,
                    package=package,
                    basket=self.request.basket,
                    prefix=settings.EXTRA_STORAGE_TEMPLATE,
                    position=settings.EXTRA_STORAGE_FEE_POSITION,
                    quantity=post_consolidation_days)


    def add_consolidation_fee(self, package):
        #add predefined consolidation fee
        predefined_quantity = package.combined_products.filter(status='predefined_packed').count()
        if predefined_quantity > 0:
            predefined_consolidation_price = D(getattr(settings, 'PREDEFINED_CONSOLIDATION_PACKAGE_FEE', '2.0'))
            create_fee_and_add_to_basket(
                title=_("Pre-Order Package Consolidation"),
                charge=predefined_consolidation_price,
                package=package,
                basket=self.request.basket,
                prefix=settings.PREDEFINED_CONSOL_TEMPLATE,
                position=settings.CONSOLIDATION_FEE_POSITION,
                quantity=predefined_quantity)

        on_demand_quantity = package.combined_products.filter(status='packed').count()
        if on_demand_quantity > 0:
            #add on demand consolidation fee
            on_demand_consolidation_price = D(getattr(settings, 'CONSOLIDATION_PACKAGE_FEE', '3.0'))
            create_fee_and_add_to_basket(
                title=_("Package Consolidation"),
                charge=on_demand_consolidation_price,
                package=package,
                basket=self.request.basket,
                prefix=settings.CONSOL_TEMPLATE,
                position=settings.CONSOLIDATION_FEE_POSITION,
                quantity=on_demand_quantity)

    def add_package_processing_fee(self, package, quantity=1):
        create_fee_and_add_to_basket(
            title=_("Package Processing"),
            charge=D(settings.PACKAGE_PROCESSING_FEE),
            package=package,
            basket=self.request.basket,
            prefix=settings.PROCESSING_TEMPLATE,
            position=settings.PACKAGE_PROCESSING_FEE_POSITION,
            quantity=quantity)

    def add_return_label_processing_fee(self, package):
        create_fee_and_add_to_basket(
            title=_("Return Label Processing"),
            charge=D(settings.RETURN_LABEL_PROCESSING_FEE),
            package=package,
            basket=self.request.basket,
            prefix=settings.RETURN_LABEL_TEMPLATE,
            position=settings.RETURN_LABEL_PROCESSING_FEE_POSITION)

    def add_eei_handling_fee(self, package):
        create_fee_and_add_to_basket(
            title=_("EEI Documentation Handling"),
            charge=D(settings.EEI_HANDLING_FEE),
            package=package,
            basket=self.request.basket,
            prefix=settings.EEI_HANDLING_TEMPLATE,
            position=settings.EEI_HANDLING_FEE_POSITION)

    def apply_offers(self, request, basket):
        basket.reset_offer_applications()
        Applicator().apply(request, basket)

    def calculate_tax(self, price, rate):
        tax = price * rate
        return tax.quantize(D('0.01'))

    def apply_tax(self, user, basket):
        profile = user.get_profile()
        if profile.country == 'ISR':
            for line in basket.all_lines():
                line_tax = self.calculate_tax(
                    line.line_price_excl_tax_incl_discounts, D('0.17'))
                unit_tax = (line_tax / line.quantity).quantize(D('0.01'))
                line.purchase_info.price.tax = unit_tax

    def handle_pending_orders(self, package):
        pending_orders = Order.objects\
            .filter(package=package, status='Pending')
        ReferralReward.objects\
            .filter(order__in=pending_orders,
                    is_active=True,
                    date_redeemed__isnull=False)\
            .update(date_redeemed=None)

    def get(self, request, *args, **kwargs):
        package = self.request.basket.get_package()
        #check that we have a linked package and it belongs to the current user
        if not package or package.owner.id != request.user.id:
            return none_package_error(request)

        #need to distinguish between a case where customer wants to return package back
        #to store and store pays for the shipping.
        #in that case customer uploads shipping label and proceed to payment without
        #entering shipping address not choosing shipping method
        if not self.checkout_session.is_return_to_store_enabled():
            # Check that the user's basket is not empty
            if self.request.basket.is_empty:
                messages.error(self.request, GENERAL_ERR)
                return HttpResponseRedirect(reverse('customer:pending-packages'))

            # Check that shipping address has been completed
            if not self.checkout_session.is_shipping_address_set():
                messages.error(request, _("Please choose a shipping address."))
                return HttpResponseRedirect(reverse('checkout:shipping-address'))

            # Check that custom form has been completed
            if not self.checkout_session.is_customs_form_set(key=package.upc):
                messages.error(self.request, _("Please fill out the customs declaration form."))
                return HttpResponseRedirect(reverse('checkout:customs'))

            # Check that shipping method has been set
            if not self.checkout_session.is_shipping_method_set(request.basket):
                messages.error(request, _("Please choose a shipping method."))
                return HttpResponseRedirect(reverse('checkout:shipping-method'))

        #Give back referral credit in case pending order exists for this package
        self.handle_pending_orders(package)

        #   Add fees
        #================
        #add consolidation fee
        if package.is_consolidated and not package.is_returned_package:
            self.add_consolidation_fee(package)
            num_of_packages = package.combined_products.all().count()
        else:
            num_of_packages = 1

        #add package processing fee
        self.add_package_processing_fee(package, num_of_packages)

        #add return label processing fee
        if self.checkout_session.is_return_to_store_prepaid_enabled():
            self.add_return_label_processing_fee(package)

        #add special requests fees
        self.add_special_request_fees(package)

        #add fixed fees
        self.add_fixed_fees(package)

        #add extra storage fee
        self.add_extra_storage_fee(package)

        #add/remove EEI handling fee (if needed)
        #no need to check return-to-merchant checkouts
        if not self.checkout_session.is_return_to_store_enabled():
            customs_form = package.customs_form
            shipping_address = self.get_shipping_address(self.request.basket)
            to_country = shipping_address.country
            if is_eei_required(customs_form, to_country):
                self.add_eei_handling_fee(package)
            else:
                #remove from basket and db
                upc = settings.EEI_HANDLING_TEMPLATE % package.upc
                try:
                    eei_fee = package.variants.get(upc=upc)
                except Product.DoesNotExist:
                    pass
                else:
                    request.basket.remove_product_line(eei_fee)
                    eei_fee.delete()

        #add combined products special requests, fixed fees and EEI handling
        count = 0
        for combined_product in package.combined_products.all():
            count += self.add_special_request_fees(
                combined_product, is_child=True, position=settings.LAST_FEE_POSITION + count)
            count += self.add_fixed_fees(
                combined_product, is_child=True, position=settings.LAST_FEE_POSITION + count)

        #apply offers to basket
        self.apply_offers(request, request.basket)

        #apply tax after offers were applied
        self.apply_tax(request.user, request.basket)

        #add message
        messages.info(request, _("Can't find the credit card billing page? "
                                 "Get help <a href='%s#pricing-q3' target='_blank'>here</a>."
                                 % reverse('faq', kwargs={'active_tab': 'pricing'})),
                      extra_tags='safe')

        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)


class PaymentDetailsView(CorePaymentDetailsView):
    preview = True

    def get_error_response(self):
        #Check that the user's basket is not empty
        if self.request.basket.is_empty:
            messages.error(self.request, GENERAL_ERR)
            return HttpResponseRedirect(reverse('customer:pending-packages'))

        # Check that shipping address has been completed
        if not self.checkout_session.is_shipping_address_set() and \
           not self.checkout_session.is_return_to_store_prepaid_enabled():
            messages.error(self.request, _("Please choose a shipping address."))
            return HttpResponseRedirect(reverse('checkout:shipping-address'))

        package = self.request.basket.get_package()
        key = package.upc
        # Check that custom form has been completed
        if not self.checkout_session.is_customs_form_set(key=key) and \
           not self.checkout_session.is_return_to_store_enabled():
            messages.error(self.request, _("Please fill out the customs declaration form."))
            return HttpResponseRedirect(reverse('checkout:customs'))

        # Check that shipping method has been set
        if not self.checkout_session.is_shipping_method_set(self.request.basket):
            messages.error(self.request, _("Please choose a shipping method."))
            return HttpResponseRedirect(reverse('checkout:shipping-method'))

    def get_context_data(self, **kwargs):
        ctx = super(PaymentDetailsView, self).get_context_data(**kwargs)
        if 'error' in ctx:
            messages.error(self.request, ctx['error'])
            #Mark that order placement process has encountered an error
            #need to redirect to pending packages page with the error
            self.has_error = True
        return ctx

    def get_shipping_method(self, basket, shipping_address=None, **kwargs):
        """
        Return the shipping method used in session
        """
        shipping_method = super(PaymentDetailsView, self).get_shipping_method(basket)
        return shipping_method

    def get_shipping_address(self, basket):
        """
        Return the shipping address as entered on our site
        """
        shipping_addr = super(PaymentDetailsView, self).get_shipping_address(basket)
        return shipping_addr

    def submit(self, user, basket, shipping_address, shipping_method,
               order_total, payment_kwargs=None, order_kwargs=None):
        """
        Since we fallback to no shipping required, we must enforce that the only case its allowed
        is when customer returns items back to merchant and he provided us with a return label
        in all other cases, we must redirect to pending packages page, display a message to the customer
        and log this incident
        """
        if shipping_method.code == 'no-shipping-required' \
            and not self.checkout_session.is_return_to_store_prepaid_enabled():
            logger.critical("Placing an order, no shipping method was found, user have been idle for too long,"
                            " user #%s" % user.id)
            messages.error(self.request, _("It seems that you've been idle for too long, please re-place your order."))
            return HttpResponseRedirect(reverse('customer:pending-packages'))

        return super(PaymentDetailsView, self).submit(user, basket, shipping_address, shipping_method,
                                                      order_total, payment_kwargs, order_kwargs)

    def load_frozen_basket(self, basket_id):
        # Lookup the frozen basket that this txn corresponds to
        try:
            basket = Basket.objects.get(id=basket_id, status=Basket.FROZEN)
        except Basket.DoesNotExist:
            return None

        # Assign strategy to basket instance
        if Selector:
            basket.strategy = Selector().strategy(self.request)

        # Re-apply any offers
        Applicator().apply(self.request, basket)

        return basket


    def unfreeze_basket(self, basket_id):
        basket = self.load_frozen_basket(basket_id)
        basket.thaw()



class ThankYouView(CoreThankYouView):
    def get(self, request, *args, **kwargs):
        if request.is_ajax():
            self.object = self.get_object()
            if self.object.status == 'Pending':
                ctx = None
            else:
                ctx = {
                    'order_status': self.object.status,
                    'order_number': self.object.number
                }
                if self.object.status == 'Cancelled':
                    try:
                        cancel_reason = OrderNote.objects\
                            .get(order=self.object, note_type='System')
                    except ObjectDoesNotExist:
                        cancel_reason = None
                    ctx['cancel_reason'] = cancel_reason
                    return self.json_response(
                        ctx=ctx, redirect_url=reverse('customer:profile-view'))
            return self.json_response(ctx=ctx)
        return super(ThankYouView, self).get(request, *args, **kwargs)

    def json_response(self, ctx, **kwargs):
        payload = kwargs
        if ctx:
            body_html = render_to_string(
                'checkout/partials/order_processing_modal_body.html',
                RequestContext(self.request, ctx))
            payload.update({'body_html': body_html})
            if ctx['order_status'] != 'Cancelled':
                footer_html = render_to_string(
                    'checkout/partials/order_processing_modal_footer.html',
                    RequestContext(self.request, ctx))
                payload.update({'footer_html': footer_html})
        return HttpResponse(json.dumps(payload),
                            mimetype="application/json")



class VoucherAddView(FormView):
    form_class = BasketVoucherForm
    voucher_model = Voucher
    add_signal = voucher_addition

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('customer:pending-packages')))

    def apply_voucher_to_basket(self, voucher):
        show_voucher = False
        if not voucher.is_active():
            messages.error(
                self.request,
                _("The '%(code)s' voucher has expired.") % {
                    'code': voucher.code})
            return True

        is_available, message = voucher.is_available_to_user(self.request.user)
        if not is_available:
            messages.error(self.request, message)
            return True

        self.request.basket.vouchers.add(voucher)

        # Raise signal
        self.add_signal.send(sender=self,
                             basket=self.request.basket,
                             voucher=voucher)

        # Recalculate discounts to see if the voucher gives any
        Applicator().apply(self.request, self.request.basket)
        discounts_after = self.request.basket.offer_applications

        # Look for discounts from this new voucher
        found_discount = False
        for discount in discounts_after:
            if discount['voucher'] and discount['voucher'] == voucher:
                found_discount = True
                break
        if not found_discount:
            messages.warning(
                self.request,
                _("Your order does not qualify for a voucher discount."))
            self.request.basket.vouchers.remove(voucher)
        else:
            messages.info(
                self.request,
                _("Voucher '%(code)s' added to basket.") % {
                    'code': voucher.code})
        return show_voucher

    def form_valid(self, form):
        code = form.cleaned_data['code']
        if not self.request.basket.id:
            return HttpResponseRedirect(reverse('checkout:payment-method') + '#voucher')
        if self.request.basket.contains_voucher(code):
            show_voucher = True
            messages.error(
                self.request,
                _("You have already added the '%(code)s' voucher to "
                  "your order.") % {'code': code})
        else:
            try:
                voucher = self.voucher_model._default_manager.get(code=code)
            except self.voucher_model.DoesNotExist:
                show_voucher = True
                messages.error(
                    self.request,
                    _("No voucher found with code '%(code)s.'") % {
                        'code': code})
            else:
                show_voucher = self.apply_voucher_to_basket(voucher)

        return HttpResponseRedirect(reverse('checkout:payment-method') + '#voucher' if show_voucher else '')

    def form_invalid(self, form):
        messages.error(self.request, _("Please enter a voucher code."))
        return HttpResponseRedirect(reverse('checkout:payment-method') + '#voucher')


class VoucherRemoveView(View):
    voucher_model = Voucher

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(reverse('customer:pending-packages'))

    def post(self, request, *args, **kwargs):
        voucher_id = int(kwargs.pop('pk'))
        if not request.basket.id:
            # Hacking attempt - the basket must be saved for it to have
            # a voucher in it.
            return HttpResponseRedirect(reverse('customer:pending-packages'))
        try:
            voucher = request.basket.vouchers.get(id=voucher_id)
        except ObjectDoesNotExist:
            messages.error(
                request, _("No voucher found with id '%d.'") % voucher_id)
        else:
            request.basket.vouchers.remove(voucher)
            request.basket.save()
            messages.info(
                request, _("Voucher '%s' removed from order.") % voucher.code)
        return HttpResponseRedirect(reverse('checkout:payment-method'))