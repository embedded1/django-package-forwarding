from django.views import generic
from paypal.adaptive.mixins import PaymentSourceMixin
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.conf import settings
from django.utils import six
from django.http import HttpResponseRedirect
from oscar.core.loading import get_class
from django.db.models import get_model
from paypal.adaptive.exceptions import (
    EmptyBasketException, MissingShippingAddressException,
    MissingShippingMethodException, InvalidBasket,
    GeneralException)
from .exceptions import BitsOfGoldError
from .gateway import register_transaction
from django.utils.translation import ugettext as _
import logging



Source = get_model('payment', 'Source')
SourceType = get_model('payment', 'SourceType')
Order = get_model('order', 'Order')
Basket = get_model('basket', 'Basket')
PaymentDetailsView = get_class('checkout.views', 'PaymentDetailsView')
CheckoutSessionMixin = get_class('checkout.session', 'CheckoutSessionMixin')
logger = logging.getLogger('bitcoin')

class RedirectView(PaymentSourceMixin,
                   generic.RedirectView,
                   PaymentDetailsView):
    """
    Initiate the transaction with BitsOfGold and redirect the user
    to BitsOfGold's website to perform the transaction.
    """
    permanent = False
    preview = False

    def get_redirect_url(self, **kwargs):
        try:
            url, token = self._get_redirect_url(**kwargs)
        except BitsOfGoldError, e:
            logger.error("BitsOfGold error: %s" % e)
            messages.error(
                self.request, _("An error occurred communicating with the Bitcoin payment processor"))
            return reverse('customer:pending-packages')
        except InvalidBasket as e:
            messages.warning(self.request, six.text_type(e))
            return reverse('customer:pending-packages')
        except EmptyBasketException:
            messages.error(self.request, _("Your basket is empty"))
            return reverse('customer:pending-packages')
        except MissingShippingAddressException:
            messages.error(
                self.request, _("A shipping address must be specified"))
            return reverse('checkout:shipping-address')
        except MissingShippingMethodException:
            messages.error(
                self.request, _("A shipping method must be specified"))
            return reverse('checkout:shipping-method')
        except GeneralException:
            messages.error(
                self.request, _("Something went terribly wrong, please try again later"))
            return reverse('customer:pending-packages')
        else:
            # Transaction successfully registered with BitsOfGold.  Now freeze the
            # basket so it can't be edited while the customer is on the BitsOfGold
            # site and flush order to the DB to eliminate incomplete transactions.
            submission = self.build_submission()
            submission['payment_kwargs'] = {'token': token}
            submission['order_kwargs'] = {'ga_client_id': self.request.POST.get('client-id')}
            self.submit(**submission)
            logger.info("Basket #%s - redirecting to %s", self.basket.id, url)
            return url

    def _get_redirect_url(self, **kwargs):
        if self.basket.is_empty:
            raise EmptyBasketException()

        #apply tax (if required) before we redirect
        self.apply_tax(self.request.user, self.basket)

        params = {
            'sender_email': self.request.user.email,
            'sender_first_name': self.request.user.first_name,
            'sender_last_name': self.request.user.last_name,
            'amount': self.basket.total_incl_tax,
            'basket_id': self.basket.id,
            'user_id': self.request.user.id
        }

        redirect_url, token = register_transaction(**params)
        if not redirect_url:
            raise BitsOfGoldError("Empty redirect url")

        return redirect_url, token

    def handle_payment(self, order_number, total, **kwargs):
        """
        Save order related data into DB
        We keep the pay key in the payment source reference attribute so we
        could finish the payment for the secondary receiver.
        Payment event contains the Pay request transaction id for audit
        The payment source stores the following:
        1 - amount_allocated = Order total value
        2 - partner_share = Partner's share
        3 - self_share = USendHome's share
        """
        # Record payment source and event
        partner_share, _ = self.get_partner_payment_info(self.basket, payment_processor=settings.BITS_OF_GOLD_LABEL)
        source_type, _ = SourceType.objects.get_or_create(name=settings.BITS_OF_GOLD_LABEL)
        source = Source(source_type=source_type,
                        currency='USD',
                        amount_allocated=total.incl_tax,
                        partner_share=partner_share,
                        self_share=total.incl_tax - partner_share,
                        label='Bitcoin',
                        reference=kwargs['token'])
        self.add_payment_source(source)
        self.add_payment_event('Settled', total.incl_tax)



class SuccessResponseView(CheckoutSessionMixin, generic.RedirectView):
    permanent = False

    def get(self, request, *args, **kwargs):
        #Order placement process has successfully finished
        # Flush all session data
        self.checkout_session.flush()
        return super(SuccessResponseView, self).get(request, *args, **kwargs)

    def get_redirect_url(self, **kwargs):
        #redirect to thank you page
        return reverse('checkout:thank-you')


class CancelResponseView(CheckoutSessionMixin, generic.RedirectView):
    permanent = False

    def delete_order(self, basket_id):
        """
        This function deletes the pending order
        """
        Order.objects.filter(basket_id=basket_id).delete()

    def get(self, request, *args, **kwargs):
        basket_id = self.checkout_session.get_submitted_basket_id()
        try:
            basket = Basket.objects.get(id=basket_id, status=Basket.SUBMITTED)
        except Basket.DoesNotExist:
            if basket_id:
                logger.error("Bitcoin cancel view: restoring basket: %s failed", basket_id)
            return HttpResponseRedirect(reverse('promotions:home'))
        basket.thaw()
        # Flush all session data
        self.checkout_session.flush()
        #self.delete_order(basket.id)
        logger.info("Payment cancelled - basket #%s thawed", basket.id)
        return super(CancelResponseView, self).get(request, *args, **kwargs)

    def get_redirect_url(self, **kwargs):
        messages.error(self.request, _("Bitcoin transaction cancelled"))
        return reverse('checkout:payment-method')
