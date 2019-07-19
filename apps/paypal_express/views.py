from paypal.express.views import SuccessResponseView as CoreSuccessResponseView
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.db.models import get_model
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from apps.paypal_express.facade import fetch_address_details
import logging
from paypal.exceptions import PayPalError

Basket = get_model('basket', 'Basket')
logger = logging.getLogger(__name__)


class SuccessResponseView(CoreSuccessResponseView):
    def verify_shipping_address(self, shipping_addr):
        #need to have 5 digits min, we add padding spaces between if needed
        padding = 5 - len(shipping_addr.postcode)
        if padding > 0:
            postcode = shipping_addr.postcode[0:-1] + padding * " " + shipping_addr.postcode[-1]
        else:
            postcode = shipping_addr.postcode
        paypal_email = self.txn.value('EMAIL')
        return fetch_address_details(paypal_email, shipping_addr.line1, postcode)

    def unfreeze_basket(self, basket_id):
        basket = self.load_frozen_basket(basket_id)
        basket.thaw()

    def is_error_message_exists(self):
        storage = messages.get_messages(self.request)
        found = False
        for msg in storage:
            if 'error' in msg.tags:
                found = True
                #fix oscar's bug where they use ugettext_lazy instead of ugettext
                #therefore, we need to evaluate the message here
                msg.message = unicode(msg.message)
                break
        storage.used = False
        return found

    def get(self, request, *args, **kwargs):
        """
        Make sure customer shipping address matches paypal shipping address and
        that the shipping address is verified by paypal
        """
        res = super(SuccessResponseView, self).get(request, *args, **kwargs)
        if isinstance(res, HttpResponseRedirect) and self.is_error_message_exists():
            #error has occurred, redirect
            return HttpResponseRedirect(reverse('customer:pending-packages'))

        basket = request.basket
        user = self.request.user
        customer_shipping_address = self.get_shipping_address(basket)
        is_return_to_merchant = self.checkout_session.is_return_to_store_enabled()

        #check that shipping address exists
        if not customer_shipping_address and not is_return_to_merchant:
            # we could not get shipping address - redirect to basket page with warning message
            logger.warning("customer's shipping address not found while verifying PayPal account")
            messages.error(self.request, _("No shipping address found, please try again."))
            self.unfreeze_basket(kwargs['basket_id'])
            return HttpResponseRedirect(reverse('checkout:shipping-address'))

        #check payer status (In some countries it is hard to get PayPal account verified
        #therefore we added an exception where we can skip this test for specific users)
        skip_account_status_test = user.get_profile().skip_pp_verified_account_test
        if not skip_account_status_test:
            payer_status = self.txn.value('PAYERSTATUS')
            if not payer_status or payer_status.lower() != 'verified':
                logger.error("unverified payer found: %s" % request.user.get_full_name())
                # unverified payer - redirect to pending packages page with error message
                messages.error(self.request, _("Your PayPal account isn't verified, please verify your account before"
                                               " proceeding to checkout."))
                return HttpResponseRedirect(reverse('customer:pending-packages'))

        #make sure the paypal email address is identical to the email address the customer
        #uses on site
        paypal_email =  self.txn.value('EMAIL')
        site_email = user.email
        if not paypal_email or not site_email or \
            paypal_email.lower() != site_email.lower():
            logger.error("paypal email address %s does not match on site email address: %s"
                         % (paypal_email, site_email))
            messages.error(self.request, _("PayPal email address does not match the email address on USendHome.com."
                                           " Please edit your settings and try again."))
            return HttpResponseRedirect(reverse('customer:pending-packages'))

        #check shipping address only for non merchant addresses
        #this check is not needed for US addresses where the package is returned to store
        if not is_return_to_merchant:
            try:
                confcode, streetmatch, zipmatch, countrycode = self.verify_shipping_address(customer_shipping_address)
            except PayPalError:
                logger.critical("PayPal address_verify api call failed")
                messages.error(self.request, _("Either the postal code or the street address is invalid.<br/>"
                                               "Make sure they both match the format you have on file at PayPal"),
                extra_tags='safe block')
                return HttpResponseRedirect(reverse('customer:pending-packages'))

            #invalid paypal email address
            if streetmatch == 'none':
                logger.error("PayPal: invalid email address")
                # we should not get here - redirect to basket page with warning message
                messages.error(self.request, _("Email address was not found on file at PayPal."))
                return HttpResponseRedirect(reverse('customer:pending-packages'))

            #check street match
            if streetmatch.lower() != 'matched':
                logger.error("PayPal: Unmatched street found")
                # unmatched street - redirect to basket page with warning message
                messages.error(self.request, _("The street address doesn't match any street address on file at PayPal.<br/>"
                                               "Make sure you deliver your package to an address listed on your PayPal account."),
                               extra_tags='safe block')
                return HttpResponseRedirect(reverse('customer:pending-packages'))

            #check postal code match
            if zipmatch.lower() != 'matched':
                logger.error("PayPal: Unmatched postal code found")
                # unmatched zip code - redirect to basket page with warning message
                messages.error(self.request, _("The postal code doesn't match any postal code on file at PayPal.<br/>"
                                               "Make sure you deliver your package to an address listed on your PayPal account."),
                               extra_tags='safe block')
                return HttpResponseRedirect(reverse('customer:pending-packages'))

            #check country match
            if countrycode != customer_shipping_address.country.iso_3166_1_a2:
                logger.error("PayPal: Unmatched shipping country, paypal country code:%s, "
                             "USendHome country code: %s" % (countrycode, customer_shipping_address.country.iso_3166_1_a2))
                # unmatched country - redirect to basket page with warning message
                messages.error(self.request, _("The destination country doesn't match any destination country on"
                                               " file at PayPal.<br/>"
                                               "Make sure you deliver your package to an address listed on your PayPal account."),
                                extra_tags='safe block')
                return HttpResponseRedirect(reverse('customer:pending-packages'))

            #check the billing country is identical to the shipping country
            #billing_country_code = self.txn.value('COUNTRY') or ''
            #if customer_shipping_address.country.iso_3166_1_a2 != billing_country_code:
            #    logger.error("PayPal: Unmatched billing country, paypal country code:%s, "
            #                 "USendHome country code: %s" % (billing_country_code, customer_shipping_address.country.iso_3166_1_a2))
            #    # unmatched country - redirect to basket page with warning message
            #    messages.error(self.request, _("The destination country doesn't match the billing address country on"
            #                                   " file at PayPal.<br/>"
            #                                   "You can only deliver your package to the country listed on your billing address."),
            #                    extra_tags='safe block')
            #    return HttpResponseRedirect(reverse('customer:pending-packages'))

            #check the billing postal code is identical to the shipping address postal code
            billing_zip = self.txn.value('ZIP') or ''
            if customer_shipping_address.postcode.upper().replace(' ', '') != billing_zip.upper().replace(' ', ''):
                logger.error("PayPal: Unmatched billing postal code, paypal postal code:%s, "
                             "USendHome postal code: %s" % (billing_zip, customer_shipping_address.postcode))
                # unmatched country - redirect to basket page with warning message
                messages.error(self.request, _("The shipping address postal code doesn't match the billing postal code"
                                               " on file at PayPal.<br/>"
                                               "You can only deliver your package to your billing postal code address."),
                                extra_tags='safe block')
                return HttpResponseRedirect(reverse('customer:pending-packages'))


        #Save billing address is session, we will use that data for MaxMind request
        request.session['paypal_billing_addr'] = {
            'billing_city': self.txn.value('CITY') or '',
            'billing_state': self.txn.value('STATE') or '',
            'billing_zip': self.txn.value('ZIP') or '',
            'billing_country': self.txn.value('COUNTRY') or ''
        }

        #all went fine continue with payment
        return res

    def post(self, request, *args, **kwargs):
        """
        catch error and unfreeze basket before redirect
        """
        res = super(SuccessResponseView, self).post(request, *args, **kwargs)
        if isinstance(res, HttpResponseRedirect) and self.is_error_message_exists():
            #error has occurred, redirect to pending packages page
            return HttpResponseRedirect(reverse('customer:pending-packages'))
        return res

    def get_context_data(self, **kwargs):
        try:
            ctx = super(SuccessResponseView, self).get_context_data(**kwargs)
        except AttributeError:
            #something went wrong  - don't return custom ctx
            return super(CoreSuccessResponseView, self).get_context_data(**kwargs)

        return ctx

    def get_shipping_method(self, basket, shipping_address=None, **kwargs):
        """
        Return the shipping method used in session
        """
        shipping_method = super(CoreSuccessResponseView, self).get_shipping_method(basket)
        return shipping_method

    def get_shipping_address(self, basket):
        """
        Return the shipping address as entered on our site
        """
        shipping_addr = super(CoreSuccessResponseView, self).get_shipping_address(basket)
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
            logger.critical("Placing an order, no shipping method was found, fallback to no shipping required,"
                            " user #%s" % user.id)
            messages.error(self.request, _("It seems that you've been idle for too long, please re-place your order."))
            return HttpResponseRedirect(reverse('customer:pending-packages'))

        return super(CoreSuccessResponseView, self).submit(user, basket, shipping_address, shipping_method,
                                                      order_total, payment_kwargs, order_kwargs)



