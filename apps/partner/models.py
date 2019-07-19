from django.db import models
from oscar.apps.address.abstract_models import AbstractPartnerAddress
from oscar.apps.partner.abstract_models import AbstractPartner
from django.utils.translation import ugettext_lazy as _
from oscar.models.fields import PhoneNumberField
from django.conf import settings


class Partner(AbstractPartner):
    @property
    def active_payment_settings(self):
        payments_settings = self.payments_settings.all().filter(is_active=True)
        if len(payments_settings) == 0:
            return None
        elif len(payments_settings) == 1:
            return payments_settings[0]
        else:
            raise NotImplementedError("Only 1 active payment settings is allowed")

    def supported_carriers(self):
        """
        For domestic deliveries we support only the USPS
        For international deliveries we return the USPS and express carriers (if available)
        """
        supported_carriers = [settings.EASYPOST_USPS]

        active_payment_settings = self.active_payment_settings
        #no express carriers, which means we only support the USPS
        if active_payment_settings is None:
            return supported_carriers

        #return all supported express carriers + USPS
        return supported_carriers + active_payment_settings.paid_carriers.split(',')

    class Meta:
        permissions = (
            ('dashboard_access', _('Can access dashboard')),
            ('support_access', _('Can access customer support dashboard')),
        )


class PartnerAddress(AbstractPartnerAddress):
    phone_number = PhoneNumberField(
        _("Phone number"), blank=True,
        help_text=_("In case we need to call you about your order"))


class PartnerOrderPaymentSettings(models.Model):
    PAYPAL, OTHER = ('paypal', 'other')
    PAYMENT_GATEWAY_CHOICES = (
        (PAYPAL, 'PayPal'),
        (OTHER, 'Other'),
    )
    partner = models.ForeignKey(
        'partner.Partner', related_name='payments_settings',
        verbose_name=_('Partner'))
    billing_email = models.EmailField(
        verbose_name=_("Email address for to receive the payment"))
    payment_gateway = models.CharField(
        verbose_name=_("Payment gateway"),
            max_length=32, choices=PAYMENT_GATEWAY_CHOICES)
    shipping_margin = models.DecimalField(
        verbose_name=_("Percentage from shipping revenues"),
        decimal_places=2, max_digits=4)
    services_margin = models.DecimalField(
        verbose_name=_("Percentage from services revenues"),
        decimal_places=2, max_digits=4)
    paid_carriers = models.CharField(
        verbose_name=_("Carriers partner pays for postage"),
        max_length=128)
    is_paying_shipping_insurance = models.BooleanField(
        verbose_name=_("Does Partner pay for shipping insurance?"),
        default=False)
    are_shipping_offers_apply = models.BooleanField(
        verbose_name=_("Do shipping offers apply to partner share?"),
        default=False)
    is_active = models.BooleanField(
        verbose_name=_("Payment settings status, only 1 settings can be active"),
        default=False)

    def __unicode__(self):
        return u"%s Payment Settings" % self.partner.name

    def postage_paid_by_partner(self, carrier):
        return carrier in self.paid_carriers.split(',')

    def build_payment_receiver(self):
        return {
            'email': self.billing_email,
            'is_primary': False
        }


from oscar.apps.partner.models import *
