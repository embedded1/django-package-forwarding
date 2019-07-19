from django.db import models
from oscar.apps.catalogue.abstract_models import AbstractProduct, ProductAttributesContainer
from .managers import PackageManager, InStorePackageManager
from .abstract_models import (
    AbstractSpecialRequests,
    AuthenticationDocument,
    AuthenticationStatus)
from django.utils.translation import ugettext_lazy as _
import logging
from django.conf import settings
from datetime import datetime
from decimal import Decimal as D
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import MaxValueValidator, MinValueValidator
from oscar.core.loading import get_classes


ProductManager, BrowsableProductManager = get_classes(
    'catalogue.managers', ['ProductManager', 'BrowsableProductManager'])
logger = logging.getLogger("management_commands")

class CustomProductAttributesContainer(ProductAttributesContainer):
    def get_all_attributes(self):
        try:
            return self.product.get_product_class().attributes.all()
        except AttributeError:
            return []

class Product(AbstractProduct):
    #owner of the product(if any - this is primary for package products)
    owner = models.ForeignKey(
        'auth.User', related_name='packages',
        blank=True, null=True)
    additional_receiver = models.ForeignKey(
        'catalogue.AdditionalPackageReceiver',
        related_name='receiver_packages',
        blank=True, null=True)
    #Children products for package consolidation
    combined_products = models.ManyToManyField(
        'catalogue.Product', blank=True, null=True,
        related_name='master',
        verbose_name=_("Combined Packages")
    )
    PERFECT, SLIGHTLY_DAMAGED, DAMAGED = (
        "Perfect", "Slightly Damaged", "Damaged")
    CONDITION_CHOICES = (
        (PERFECT, _(PERFECT)),
        (SLIGHTLY_DAMAGED, _(SLIGHTLY_DAMAGED)),
        (DAMAGED, _(DAMAGED)))
    NO_BATTERY, INSTALLED_BATTERY, LOOSE_BATTERY = (
        "No Battery", "Installed Battery", "Loose Battery"
    )
    BATTERY_CHOICES = (
        (NO_BATTERY, _(NO_BATTERY)),
        (INSTALLED_BATTERY, _(INSTALLED_BATTERY)),
        (LOOSE_BATTERY, _(LOOSE_BATTERY))
    )
    condition = models.CharField(
        _("parcel Condition"), max_length=128,
        choices=CONDITION_CHOICES, default=CONDITION_CHOICES[0][0])
    is_client_id_missing = models.NullBooleanField(
        _("Suite number missing?"), default=False)
    is_contain_prohibited_items = models.NullBooleanField(
        _("Package contains prohibited items?"), default=False)
    battery_status = models.CharField(
        _("Package contains lithium battery?"), max_length=32,
        choices=BATTERY_CHOICES, default=BATTERY_CHOICES[0][0])
    is_sent_outside_usa = models.NullBooleanField(
        _("Package was sent outside of the US?"), default=False)
    date_consolidated = models.DateTimeField(
        _("Date Consolidated"), blank=True, null=True)
    shopify_store_id = models.IntegerField(
        _("Shopify store ID - this is the link between a package and"
          " shopify store that was sending it"), blank=True, null=True, db_index=True)
    merchant_zipcode = models.CharField(
        _("Merchant zip code (enter only numbers)"), max_length=64,
        blank=True, null=True, db_index=True)


    objects = ProductManager()
    browsable = BrowsableProductManager()
    packages = PackageManager()
    in_store_packages = InStorePackageManager()

    def __init__(self, *args, **kwargs):
        super(AbstractProduct, self).__init__(*args, **kwargs)
        self.attr = CustomProductAttributesContainer(product=self)

    @property
    def is_consolidated(self):
        return self.combined_products.all().exists()

    @property
    def is_initial_consolidated_package_status(self):
        return self.status == 'consolidation_taking_place'

    @property
    def is_waiting_for_consolidation(self):
        return self.status == 'predefined_waiting_for_consolidation' or\
               self.status == 'waiting_for_consolidation'
    @property
    def is_predefined_waiting_for_consolidation(self):
        return self.status == 'predefined_waiting_for_consolidation'

    @property
    def is_single(self):
        return not self.is_consolidated and\
               not self.is_waiting_for_consolidation

    @property
    def is_returned_package(self):
        return self.status == 'pending_returned_package'

    @property
    def weight(self):
        return getattr(self.attr, 'weight', '0.0')

    @property
    def height(self):
        return getattr(self.attr, 'height', '0.0')

    @property
    def width(self):
         return getattr(self.attr, 'width', '0.0')

    @property
    def length(self):
        return getattr(self.attr, 'length', '0.0')

    @property
    def is_envelope(self):
        return getattr(self.attr, 'is_envelope', False)

    @property
    def custom_form_summary(self):
        """
        Returns tuple of contents type and list of items
        """
        try:
            return self._customs_form_content()
        except (AttributeError, ObjectDoesNotExist):
            return None, []

    @property
    def partner(self):
        try:
            return self.stockrecords.all()[0].partner
        except IndexError:
            return None

    @property
    def is_package(self):
        try:
            return self.product_class.name == 'package'
        except ObjectDoesNotExist:
            return False

    @property
    def is_contain_lithium_battery(self):
        return self.battery_status != self.NO_BATTERY

    def total_content_value(self):
        try:
            return self.customs_form.total_content_value()
        except (AttributeError, ObjectDoesNotExist):
            return D('0.0')

    def __unicode__(self):
        """
        For packages we will return the upc field for all other products (fees)
        we will return the title
        """
        if self.is_package:
            return self.upc
        return self.title

    def is_ready_for_checkout(self):
        return self.status.startswith('pending')

    def get_type(self):
        if self.is_consolidated:
            return "Consolidated"
        elif self.is_waiting_for_consolidation:
            return "Waiting for Consolidation"
        return "Single"

    def latest_order(self):
        try:
            return self.orders.all().order_by('-date_placed')[0]
        except IndexError:
            pass
        return None

    def _customs_form_content(self):
        return self.customs_form.content()

    def calculate_date_created(self, children):
        """
        Return the date created of product
        Special case for consolidated package that contains children packages
        where we need to return the first date_created among children
        """
        first_date_created = self.date_created or datetime.now()

        for product in children:
            if product.date_created < first_date_created:
                first_date_created = product.date_created
        return first_date_created

    def create_consolidated_package_title(self, children):
        """
        Combine all merchants together, limit to 255 characters
        """
        all_merchants =  u", ".join(
            map(lambda x: x.title.title(), children))
        return (all_merchants[:252] + '...') if len(all_merchants) > 255 else all_merchants

    def customs_form_data(self):
        try:
            customs_form_data = self.customs_form.customs_form_data()
        except ObjectDoesNotExist:
            customs_form_data = {}
        return customs_form_data

    def combined_products_quantity(self):
        return self.combined_products.all().count()


    def has_special_requests(self):
        try:
            self.special_requests
        except ProductSpecialRequests.DoesNotExist:
            return False
        #else:
        #    return self.special_requests.is_repackaging or\
        #           self.special_requests.is_custom_requests

    def has_customs_form(self):
        try:
            self.customs_form
        except ProductCustomsForm.DoesNotExist:
            return False
        else:
            return self.customs_form is not None

    def has_customs_form_items(self):
        return self.has_customs_form() and self.customs_form.items.all().exists()

    def has_image(self):
        return self.images.all().exists()

    def has_consolidation_requests(self):
        try:
            self.consolidation_requests
        except ProductConsolidationRequests.DoesNotExist:
            return False
        else:
            return self.consolidation_requests is not None

    def get_storage_days(self):
        """
        Returns the number of days the package is stored
        Only valid for packages currently in warehouse
        """
        #get only year month and day
        now = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0)
        #get only year month and day
        date_created = self.date_created.replace(
            hour=0, minute=0, second=0, microsecond=0)
        storage_time = now - date_created
        return storage_time.days

    def get_post_consolidation_days(self):
        """
        Returns the number of days a consolidated package is stored
        starting from the time we completed the consolidation request
        """

        #sanity check, make sure package is consolidated and date_consolidated available
        if not self.is_consolidated or not self.date_consolidated:
            return -1

        #get only year month and day
        now = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0)
        #get only year month and day
        date_consolidated = self.date_consolidated.replace(
            hour=0, minute=0, second=0, microsecond=0)
        post_consolidation_time = now - date_consolidated
        return post_consolidation_time.days

    def number_of_post_consolidation_delivery_days(self):
        post_consolidation_days = self.get_post_consolidation_days()
        #make sure package is consolidated, otherwise return -1
        if post_consolidation_days < 0:
            return post_consolidation_days
        return settings.ALERT_PACKAGE_CONSOLIDATION_DELIVERY_DAYS_LEFT - post_consolidation_days

    def number_of_free_storage_days_left(self):
        storage_days = self.get_storage_days()
        #consolidated packages have 30 days free of storage while other packages have 10 days
        if self.is_consolidated:
            max_allowed_days = getattr(settings, 'CONSOLIDATED_FREE_STORAGE_IN_DAYS', 30)
        else:
            max_allowed_days = getattr(settings, 'FREE_STORAGE_IN_DAYS', 10)
        return max_allowed_days - storage_days

    def flat_rate_shipping_methods_applicable(self):
        """
        Currently flat rate box is not applicable for consolidated packages and
        for repacked packages
        """
        try:
            special_requests = self.special_requests
        except ProductSpecialRequests.DoesNotExist:
            special_requests = None

        return not (self.is_consolidated or (special_requests and special_requests.repackaging_done))

    def pending_special_requests_list(self):
        try:
            return self.special_requests.pending_special_requests(include_express_checkout=True)
        except (AttributeError, ProductSpecialRequests.DoesNotExist):
            return []

    def pending_special_requests_summary(self, include_express_checkout=False):
        try:
            return self.special_requests.pending_special_requests_summary(include_express_checkout)
        except (AttributeError, ProductSpecialRequests.DoesNotExist):
            return u""

    def completed_special_requests_list(self):
        try:
            return self.special_requests.completed_special_requests()
        except (AttributeError, ProductSpecialRequests.DoesNotExist):
            return []

    def fulfilled_special_requests_list(self):
        try:
            return self.special_requests.fulfilled_special_requests()
        except (AttributeError, ProductSpecialRequests.DoesNotExist):
            return []

    def get_customized_services_brief(self):
        """
        Show brief if the warehouse has written something
        """
        try:
            return self.special_requests.custom_requests_details
        except ProductSpecialRequests.DoesNotExist:
            return None

    def get_customized_services(self):
        try:
            return self.special_requests.is_custom_requests
        except ProductSpecialRequests.DoesNotExist:
            return None

    def has_additional_receiver(self):
        try:
            self.additional_receiver
        except AdditionalPackageReceiver.DoesNotExist:
            return False
        else:
            return self.additional_receiver is not None

    def receiver_verified(self):
        """
        We support additional package receivers, if such receiver exists we must
        make sure the additional receiver is verified
        for consolidated package we check if the combined products all have verified receivers
        """
        if not self.has_additional_receiver():
            return True
        return self.additional_receiver.verification_status == AdditionalPackageReceiver.VERIFIED

    def receiver_verification_required(self):
        if not self.has_additional_receiver():
            return False
        return self.additional_receiver.verification_status ==\
            AdditionalPackageReceiver.UNVERIFIED

    def receiver_verification_in_process(self):
        if not self.has_additional_receiver():
            return False
        return self.additional_receiver.verification_status == \
            AdditionalPackageReceiver.VERIFICATION_IN_PROGRESS

    def receiver_verification_failed(self):
        if not self.has_additional_receiver():
            return False
        return self.additional_receiver.verification_status == \
            AdditionalPackageReceiver.VERIFICATION_FAILED

    def receiver_verification_requires_more_docs(self):
        if not self.has_additional_receiver():
            return False
        return self.additional_receiver.verification_status == \
            AdditionalPackageReceiver.WAITING_FOR_MORE_DOCUMENTS

    def all_additional_receivers_names(self):
        """
        Get all additional receivers all_names
        Support consolidated and single packages
        """
        all_names = set()

        if self.has_additional_receiver():
            all_names.add(self.additional_receiver.get_full_name())

        for package in self.combined_products.all():
            if package.has_additional_receiver():
                all_names.add(package.additional_receiver.get_full_name())

        return all_names


class ProductCustomsForm(models.Model):
    GIFT, MERCHANDISE, RETURNED_GOODS = ("Gift", "Merchandise", "Returned Goods")
    TYPE_CHOICES = (
        (GIFT, _(GIFT)),
        (MERCHANDISE, _(MERCHANDISE)),
        (RETURNED_GOODS, _(RETURNED_GOODS))
    )
    #we allow None value for consolidated packages where we collect all CustomItems
    #from inner pcakges but let the customer select the content_type
    content_type = models.CharField(
        _("Content type"), max_length=128, choices=TYPE_CHOICES)
    #Customs form  that goes along with package
    package = models.OneToOneField(
        'catalogue.Product', related_name='customs_form',
        null=True, verbose_name=_("Package")
    )
    date_created = models.DateTimeField(_("Date created"), auto_now_add=True)

    def customs_form_data(self):
        data = {'content_type': self.content_type}
        for i, item in enumerate(self.items.all().order_by('date_created')):
            data.update({
                'content_desc%s' % i: item.description,
                'content_quantity%s' % i: item.quantity,
                'content_value%s' % i: item.value
            })
        return data

    def content(self):
        content = []
        for desc, val, quantity in self.items.all().values_list('description', 'value', 'quantity'):
            content.append(desc)
            content.append(quantity)
            content.append(val)
        return self.content_type, content

    def remove_items(self):
        self.items.all().delete()

    def total_content_value(self):
        return self.items.all().aggregate(total=Sum('value'))['total']

    def missing_item_value_exists(self):
        return self.items.filter(value=0).exists()

    def is_eei_required(self):
        """
        Returns true if any item's value is greater than $2500
        """
        for item in self.items.all():
            if item.value > D(settings.CONTENTS_VALUE_EEI_REQUIRED):
                return True
        return False

    def __unicode__(self):
        return u"Customs Declaration of package %s" % self.package

    class Meta:
        verbose_name = _('Customs Form')
        verbose_name_plural = _('Customs Forms')


class CustomsFormItem(models.Model):
    quantity = models.PositiveIntegerField(
        _('Quantity'), validators=[MinValueValidator(1), MaxValueValidator(999)])
    description = models.CharField(
        _("Detailed description"), max_length=128)
    value = models.DecimalField(
        _("Total value (1 item value x quantity)"),
        decimal_places=2, max_digits=6)
    hs_tariff_number = models.CharField(
        _("harmonized system for tariffs number"), max_length=6,
        blank=True, null=True)
    customs_form = models.ForeignKey(
        'catalogue.ProductCustomsForm', related_name='items',
        verbose_name=_("Customs Form"))
    date_created = models.DateTimeField(
        _("Date created"), auto_now_add=True)

    class Meta:
        verbose_name = _('Customs Form Item')
        verbose_name_plural = _('Customs Form Items')

    def __unicode__(self):
        return u"%s" % self.description


class ProductSpecialRequests(AbstractSpecialRequests):
    """
    Gather special requests for single package
    """
    package = models.OneToOneField(
        'catalogue.Product', related_name='special_requests',
        verbose_name=_("Product"), blank=True, null=True)
    date_created = models.DateTimeField(_("Date Created"), auto_now_add=True)
    date_updated = models.DateTimeField(_("Date Updated"), auto_now=True, db_index=True)


    class Meta:
        verbose_name = _('Product Special Requests')
        verbose_name_plural = verbose_name

    def __unicode__(self):
        return u"Special requests:%s of '%s'" % (self.pending_special_requests_summary(
            include_express_checkout=True), self.package)


class ProductConsolidationRequests(models.Model):
    """
    Gather special requests for consolidated package
    """
    package = models.OneToOneField(
        'catalogue.Product',
        verbose_name=_("Product"),
        related_name='consolidation_requests')
    KEEP_PACKING, REMOVE_PACKING = ('Keep', 'Remove')
    ITEM_PACKING_CHOICES = (
        (KEEP_PACKING, _("Keep items packing")),
        (REMOVE_PACKING, _("Remove items packing"))
    )
    item_packing = models.CharField(
        _("What do you want us to do with the in box packing?"),
        max_length=64, choices=ITEM_PACKING_CHOICES,
        default=ITEM_PACKING_CHOICES[0][0])
    MULTIPLE_BOXES, ONE_BOX = ('Multiple boxes', 'One box')
    CONTAINER_CHOICES = (
        (ONE_BOX, _("Use 1 box for all of my items")),
        (MULTIPLE_BOXES, _("Split my items into multiple boxes to"
                           " meet USPS size limit"))
    )
    container = models.CharField(
        _("How do you want us to deliver your items?"),
        max_length=64, choices=CONTAINER_CHOICES,
        default=CONTAINER_CHOICES[0][0],
        help_text=_("Don't forget to select option #2 if you want us to deliver"
                    " your items through the USPS "))
    date_created = models.DateTimeField(_("Date Created"), auto_now_add=True)

    def get_selected_choice(self, attr, choices):
        for key, value in choices:
            if getattr(self, attr, '') == key:
                return value
        return ''

    def pending_requests(self):
        pending = []
        pending.append(unicode(self.get_selected_choice('item_packing', self.ITEM_PACKING_CHOICES)))
        pending.append(unicode(self.get_selected_choice('container', self.CONTAINER_CHOICES)))
        return pending

    def pending_requests_summary(self):
        return u", ".join(self.pending_requests())

    class Meta:
        verbose_name = _('Product Consolidation Requests')
        verbose_name_plural = verbose_name
        ordering = ['date_created']

    def __unicode__(self):
        return u"Requests:%s of '%s'" % (self.pending_requests_summary(), self.package)

class ProductPackagingImage(models.Model):
    product = models.ForeignKey(
        'catalogue.Product', related_name='packaging_images', verbose_name=_("Product"))
    original = models.ImageField(_("Original"),
                                 upload_to=settings.PRODUCT_PACKAGING_IMAGE_FOLDER, max_length=255)
    caption = models.CharField(
        _("Caption"), max_length=200, blank=True, null=True)

    #: Use display_order to determine which is the "primary" image
    display_order = models.PositiveIntegerField(
        _("Display Order"), default=0,
        help_text=_("An image with a display order of zero will be the primary"
                    " image for a product"))
    date_created = models.DateTimeField(_("Date Created"), auto_now_add=True)

    class Meta:
        unique_together = ("product", "display_order")
        ordering = ["display_order"]
        verbose_name = _('Product Packaging Image')
        verbose_name_plural = _('Product Packaging Images')

    def __unicode__(self):
        return u"Packaging Image of '%s'" % self.product

    def is_primary(self):
        """
        Return bool if image display order is 0
        """
        return self.display_order == 0


class AdditionalPackageReceiver(AuthenticationStatus):
    package_owner = models.ForeignKey(
        'auth.User', related_name='additional_receivers')
    first_name = models.CharField(
        _('first name'), max_length=30,
        db_index=True)
    last_name = models.CharField(
        _('last name'), max_length=30,
         db_index=True)

    class Meta:
        verbose_name = _('Additional Package Receiver')
        verbose_name_plural = _('Additional Package Receivers')
        unique_together = ("package_owner", "first_name", "last_name")

    def __unicode__(self):
        return u"Package receiver %s of package owner %s" % (
            self.get_full_name(), self.package_owner)

    def get_full_name(self):
        full_name = "%s %s" % (self.first_name, self.last_name)
        return full_name.strip().title()

class PackageReceiverDocument(AuthenticationDocument):
    """
    A shipping label image of a product
    """
    receiver = models.ForeignKey(
        'catalogue.AdditionalPackageReceiver', related_name='documents',
        verbose_name=_("Package receiver"), null=True)

    def __unicode__(self):
        return u"%s document of %s" % (self.category, self.receiver)

    class Meta:
        verbose_name = _('Package Receiver Authentication Document')
        verbose_name_plural = _('Package Receiver Authentication Documents')

class PackageLocation(models.Model):
    USH, MAIN = ("USH", "Main")
    WAREHOUSE_CHOICES = (
        (USH, USH),
        (MAIN, MAIN),
    )
    package = models.OneToOneField(
        'catalogue.Product', related_name='location')
    warehouse = models.CharField(
        _("Warehouse name"), max_length=64,
        choices=WAREHOUSE_CHOICES, default=WAREHOUSE_CHOICES[0][0])
    loc1 = models.CharField(
        _("Location 1"), max_length=64)
    loc2 = models.CharField(
        _("Location 2"), max_length=64,
        blank=True, null=True)
    loc3 = models.CharField(
        _("Location 3"), max_length=64,
        blank=True, null=True)

    def printable_location(self):
        location_tokens = [self.warehouse, self.loc1, self.loc2, self.loc3]
        return "-".join(token for token in location_tokens if token)

    def __unicode__(self):
        return u"Location: [%s,%s,%s] of package #%s" % (
            self.loc1, self.loc2, self.loc3, self.package.upc)



from oscar.apps.catalogue.models import *

