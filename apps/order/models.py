from oscar.apps.order.abstract_models import AbstractOrder, AbstractLine
from oscar.apps.address.abstract_models import AbstractShippingAddress
from apps.address.models import PostCodesRegex
from django.db import models
from django.utils.translation import ugettext_lazy as _
from collections import namedtuple
from django.core.exceptions import ValidationError
from django.conf import settings
import os

class ShippingAddress(PostCodesRegex, AbstractShippingAddress):
    def ensure_postcode_is_valid_for_country(self):
        """
        Validate postcode given the country
        Only when postcode was missing and the addresses in country
        require a postcode
        Currently, we removed Oscar's postcode validation
        """
        if not self.postcode and self.country_id:
            country_code = self.country.iso_3166_1_a2
            regex = self.POSTCODES_REGEX.get(country_code, None)
            if regex:
                msg = _("Addresses in %(country)s require a valid postcode") \
                    % {'country': self.country}
                raise ValidationError(msg)

class Line(AbstractLine):
    #we need to set basket position for products
    #for example: we would like to enforce that the shipping method cost will be shown first
    #and then shipping insurance cost (if any) and so on
    position = models.PositiveIntegerField(_("Position in order"), default=0)

    class Meta:
        ordering = ["position"]


class Order(AbstractOrder):
    #link to order for management actions (for package products)
    package = models.ForeignKey(
        'catalogue.Product', related_name="orders",
        blank=True, null=True)
    #shipping insurance not always selected
    shipping_insurance = models.BooleanField(
        _("Shipping insurance"), default=False)
    # Shipping insurance charges
    shipping_insurance_incl_tax = models.DecimalField(
        _("Shipping insurance charge (inc. tax)"), decimal_places=2, max_digits=12,
        default=0)
    shipping_insurance_excl_tax = models.DecimalField(
        _("Shipping insurance charge (excl. tax)"), decimal_places=2, max_digits=12,
        default=0)
    shipping_surcharges = models.CharField(
        max_length=256, verbose_name=_("All surcharges applied"),
        blank=True, null=True)
    shipping_insurance_claim_issued = models.BooleanField(
        _("Is shipping insurance claim was issued for this order"), default=False)
    risk_score = models.DecimalField(
        verbose_name=_("MaxMind Order Risk Score"), decimal_places=2,
        max_digits=5, default=0)
    maxmind_trans_id = models.CharField(
        _("Maxmind minFraud transaction ID"),
        max_length=16, null=True, blank=True)
    feedback_request_sent = models.BooleanField(
        _("Was feedback request sent?"), default=False)
    date_feedback_request_sent = models.DateTimeField(
        _("Date Feedback request sent"), null=True, blank=True)
    ga_client_id = models.CharField(
        _("Google Analytics Client ID"), max_length=64,
        null=True, blank=True)
    is_incomplete_customs_declaration = models.BooleanField(
        _("Order contains incomplete customs declaration?"), default=False)
    # we also save shipping country here to save DB access for GlobalShipped Shopify app
    shipping_country = models.CharField(
        _('Order destination country'), blank=True, null=True, max_length=128)

    def is_shipped(self):
        return self.status in [
            'Shipped', 'Delivered',
            'Return to sender', 'Failure',
            'Out for delivery', 'Available for pickup',
        ]

    def latest_shipping_label(self):
        return self.labels.all().latest(field_name='date_created')

    def shipping_label_exists(self):
        return self.labels.all().exists()

    def partner_waits_for_payment(self):
        return self.get_payment_source_type() in ("PayPal", ) and\
               self.get_partner_share() > 0 and \
               (self.is_prepaid_return_to_store() or not self.shipping_label_exists())

    def partner_paid_for_shipping(self):
        partner = self.package.partner
        partner_payment_settings = partner.active_payment_settings
        carrier = self.tracking.carrier
        return partner_payment_settings.postage_paid_by_partner(carrier)

    def get_payment_source(self):
        return self.sources.all()[0]

    def get_payment_source_type(self):
         return self.get_payment_source().source_type.name

    def get_usendhome_share(self):
        return self.get_payment_source().self_share

    def get_partner_share(self):
        return self.get_payment_source().partner_share

    def get_pay_key(self):
        pay_key = None
        payment_source = self.get_payment_source()
        if payment_source.source_type.name == 'PayPal':
            pay_key = payment_source.reference
        return pay_key

    def is_return_to_store(self):
        return self.shipping_address is not None and\
               'RETURN ADDRESS' in self.shipping_address.first_name

    def is_prepaid_return_to_store(self):
        return self.shipping_code == 'no-shipping-required'

    def get_applied_referral_credit(self):
        discounts = self.basket_discounts
        for discount in discounts:
            if discount.offer_name == 'Referral Program':
                return discount.amount
        return D('0.00')

    def is_eei_document_required(self):
        package = self.package
        if package and package.has_customs_form():
            customs_form = package.customs_form
            to_country = self.shipping_address.country
            from apps.shipping.utils import is_eei_required
            return is_eei_required(customs_form, to_country)
        return False

    def shipping_margin(self):
        return self.shipping_incl_tax - self.shipping_excl_tax

    def shipping_insurance_margin(self):
        return self.shipping_insurance_incl_tax - self.shipping_insurance_excl_tax


class ShippingLabelBatch(models.Model):
    """
        A model to hold batch information.
    """
    STATUS = namedtuple(
    'STATUS', 'queued label_generating label_generated label_downloaded label_printed label_refunded'
              ' api_failed creation_failed purchase_failed'
    )._make(range(9))

    STATUS_CHOICES = [
        (STATUS.queued, 'queued'), (STATUS.label_generating, 'label_generating'),
        (STATUS.label_generated, 'label_generated'), (STATUS.label_downloaded, 'label_downloaded'),
        (STATUS.label_printed, 'label_printed'), (STATUS.label_refunded, 'label_refunded'),
        (STATUS.api_failed, 'api_failed'), (STATUS.creation_failed, 'creation_failed'),
        (STATUS.purchase_failed, 'purchase_failed'),
    ]

    batch_id = models.CharField(
        _("Batch ID"), max_length=64)
    orders = models.ManyToManyField(
        'order.Order', related_name='batches',
        verbose_name=_('Orders'))
    status = models.PositiveSmallIntegerField(
        choices=STATUS_CHOICES, db_index=True,
        default=STATUS.queued)
    shipping_label = models.FileField(
        _("Batch shipping label"),
        upload_to=settings.BATCH_SHIPPING_LABEL_FOLDER,
        blank=True, null=True)
    partner = models.ForeignKey(
        'partner.Partner', related_name='batches',
        blank=True, null=True)
    date_created = models.DateTimeField(
        _("Date Created"), auto_now_add=True)
    date_updated = models.DateTimeField(
        _("Date Updated"), auto_now=True)

    def __unicode__(self):
        return u"%s" % self.batch_id

    class Meta:
        verbose_name = _('Shipping Label Batch')
        verbose_name_plural = _('Shipping Label Batches')


class OrderTracking(models.Model):
    order = models.OneToOneField(
        'order.Order', related_name='tracking',
        verbose_name=_("Order"))
    tracking_number = models.CharField(
        _("Tracking Number"), max_length=64,
        blank=True, null=True)
    shipment_id = models.CharField(
        _("EasyPost Shipment ID"), max_length=64,
        blank=True, null=True)
    carrier = models.CharField(
        _("Selected Carrier"), max_length=64)
    display_carrier = models.CharField(
        _("Selected Display Carrier"), max_length=64, default='')
    itn_number = models.CharField(
        _("Internal Transaction Number - required for shipments valued over $2500"),
        max_length=32, blank=True, null=True)
    contents_explanation = models.CharField(
        _("Human readable description of content"),
        max_length=255, blank=True, null=True
    )

    def __unicode__(self):
        return u"Tracking data of order %s" % self.order

class ShippingLabel(models.Model):
    """
    A shipping label image of a product
    """
    order = models.ForeignKey(
        'order.Order', related_name='labels',
        verbose_name=_("Order"), null=True)
    original = models.FileField(
        _("Shipping label"), upload_to=settings.SHIPPING_LABEL_FOLDER)
    caption = models.CharField(
        _("Caption"), max_length=200, blank=True, null=True)
    date_created = models.DateTimeField(_("Date Created"), auto_now_add=True)

    class Meta:
        verbose_name = _('Product Shipping Label')
        verbose_name_plural = _('Product Shipping Label')

    def __unicode__(self):
        return u"Shipping label of order %s" % self.order

    def filename(self):
        return os.path.basename(self.original.name)

    def resized_image_url(self, width=None, height=None, **kwargs):
        return self.original.url

    @property
    def fullsize_url(self):
        """
        Returns the URL path for this image.  This is intended
        to be overridden in subclasses that want to serve
        images in a specific way.
        """
        return self.resized_image_url()

    @property
    def thumbnail_url(self):
        return self.resized_image_url()



class ExpressCarrierCommercialInvoice(models.Model):
    order = models.ForeignKey(
        'order.Order', related_name='commercial_invoices',
        verbose_name=_('Order that the commercial invoice belongs to'),
        null=True)
    original = models.FileField(
        _("Commercial invoice"), upload_to=settings.COMMERCIAL_INVOICE_FOLDER)
    date_created = models.DateTimeField(_("Date Created"), auto_now_add=True)

    class Meta:
        verbose_name = _('Commercial Invoice')
        verbose_name_plural = _('Commercial Invoices')

    def __unicode__(self):
        return u"Commercial invoice of order %s" % self.order

    def filename(self):
        return os.path.basename(self.original.name)

from .receivers import *
from oscar.apps.order.models import *
