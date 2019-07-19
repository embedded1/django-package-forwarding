from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ValidationError
from django.conf import settings
import os


class AbstractSpecialRequests(models.Model):
    NULL_BOOLEAN_FIELDS = ['is_custom_requests', 'is_repackaging', 'is_remove_invoice', 'is_extra_protection']
    NO_PHOTO, SINGLE_PHOTO, THREE_PHOTOS = 'Zero', 'One', 'Three'
    choices = (
        (NO_PHOTO, _('No Photos')),
        (SINGLE_PHOTO, _('1 Photo ($2)')),
        (THREE_PHOTOS, _('3 Photos ($5)')))
    is_filling_customs_declaration = models.BooleanField(
        _("Customs Declaration Paperwork ($5)"), default=False,
        help_text=_("Customs declarations have to be filled out; we'll do it for you"))
    filling_customs_declaration_done = models.BooleanField(
        _("Customs Declaration Paperwork completed?"), default=False)
    is_repackaging = models.BooleanField(
        _("Repacking ($5)"), default=False,
        help_text=_("Have us repack your order into cost-saving containers."))
    repackaging_done = models.NullBooleanField(
        _("Package repacked?"), null=True, blank=True)
    is_express_checkout = models.BooleanField(
        _("Express Checkout ($2)"), default=False, db_index=True,
        help_text=_("Move your package(s) to the head of the shipping line"))
    express_checkout_done = models.BooleanField(
        _("Express Checkout Completed?"), default=False, db_index=True)
    is_remove_invoice = models.BooleanField(
        _("Remove Invoice ($1)"), default=False, db_index=True,
        help_text=_("We'll remove the original invoice out of your package"))
    remove_invoice_done = models.NullBooleanField(
        _('Is invoice removed?'), null=True, blank=True)
    is_extra_protection = models.BooleanField(
        _("Extra Protection ($2)"), default=False, db_index=True,
        help_text=_("Add layers of protection to ensure breakables make it safely overseas"))
    extra_protection_done = models.NullBooleanField(
        _('Is extra protection added?'), null=True, blank=True)
    is_photos = models.CharField(
        _("Package Content Photos"),
        choices=choices, help_text=_("Ensure you got exactly what you ordered with content snapshots"),
        default=NO_PHOTO, max_length=16)
    photos_done = models.BooleanField(
        _("Contents photos taken?"), default=False)
    is_custom_requests = models.TextField(
        verbose_name=_('Customized Services ($5)'), blank=True,
        null=True, help_text=_("Want something special to suit your specific needs? Just ask"))
    custom_requests_done = models.NullBooleanField(
        _('Is At Least 1 customized service Fulfilled?'), null=True, blank=True)
    custom_requests_details = models.TextField(
        verbose_name=_('Customized Services Summary'), blank=True, null=True,
        help_text=_("Please briefly describe the actions that were taken on the items, it will be displayed"
                    " as-is to the customer"))


    @property
    def is_photos_required(self):
        return self.is_photos != self.NO_PHOTO

    def get_number_of_photos(self):
        if self.is_photos == self.SINGLE_PHOTO:
            return 1
        if self.is_photos == self.THREE_PHOTOS:
            return 3
        return 0

    def get_photos_extra_service_desc(self):
        num_of_photos = self.get_number_of_photos()
        if num_of_photos == 1:
            return unicode(self.choices[1][1])
        elif num_of_photos == 3:
            return unicode(self.choices[2][1])
        return ''

    def special_requests_walk(self, collect_pending, include_express_checkout):
        res = []
        for field in self._meta.fields:
            if "is_" in field.name and getattr(self, field.name):
                if field.name == 'is_photos':
                    if self.get_number_of_photos() == 0:
                        continue
                #check that the special request has already completed
                base_field_name = field.name.split('_', 1)[1]
                done_field_name = base_field_name + '_done'
                is_done = getattr(self, done_field_name)
                #special case for repacking and custom requests where False marks that
                #they were processed and we should not consider them as pending
                if field.name in self.NULL_BOOLEAN_FIELDS:
                    is_done = False if is_done is None else True
                if not ((is_done and not collect_pending) or (is_done is False and collect_pending)):
                    continue
                if 'express_checkout' in field.name and not include_express_checkout:
                    continue
                #special case for taking photos request which splits into 2 options
                if field.name == 'is_photos':
                    if self.is_photos_required:
                        res.append(self.get_photos_extra_service_desc())
                else:
                    res.append(unicode(field.verbose_name))
        return res

    def fulfilled_special_requests(self):
        res = []
        for field in self._meta.fields:
            if "done" in field.name and getattr(self, field.name):
                base_field_name = field.name.rsplit('_', 1)[0]
                is_field_name = 'is_' + base_field_name
                #special case for taking photos request which splits into 2 options
                if is_field_name == 'is_photos':
                    if self.is_photos_required:
                        res.append(self.get_photos_extra_service_desc())
                else:
                    res.append(unicode(self._meta.get_field(is_field_name).verbose_name))
        return res

    def pending_special_requests(self, include_express_checkout=False):
        return self.special_requests_walk(collect_pending=True,
                                          include_express_checkout=include_express_checkout)

    def pending_special_requests_summary(self, include_express_checkout=False):
        return u", ".join(self.pending_special_requests(include_express_checkout=include_express_checkout))

    def completed_special_requests(self):
        return self.special_requests_walk(collect_pending=False,
                                          include_express_checkout=True)

    def is_special_request_required(self, special_request):
        if 'is_photos' == special_request:
            return self.is_photos_required
        return getattr(self, special_request, False)

    def is_special_request_fulfilled(self, special_request):
        return getattr(self, special_request, False)

    def requested_special_requests_attr_names(self):
        """
        return a list of requested special requests
        """
        requested = []
        for field in self._meta.fields:
            if "is_" in field.name:
                if self.is_special_request_required(field.name):
                    requested.append(field.name)
        return requested

    def is_show_special_requests_tab(self):
        for field_name in self.NULL_BOOLEAN_FIELDS:
            if getattr(self, field_name, False):
                return True
        return False

    class Meta:
        abstract = True
        verbose_name = _('Product Special Requests')
        verbose_name_plural = verbose_name


class AuthenticationStatus(models.Model):
    UNVERIFIED, VERIFICATION_IN_PROGRESS,\
    WAITING_FOR_MORE_DOCUMENTS, VERIFICATION_FAILED, VERIFIED = (
        "Unverified", "Reviewing Documents",
        "Waiting for More Documents",
        "Failed", "Verified")
    VERIFICATION_STATUS_CHOICES = (
        (UNVERIFIED, _(UNVERIFIED)),
        (VERIFICATION_IN_PROGRESS, _(VERIFICATION_IN_PROGRESS)),
        (WAITING_FOR_MORE_DOCUMENTS, _(WAITING_FOR_MORE_DOCUMENTS)),
        (VERIFICATION_FAILED, _(VERIFICATION_FAILED)),
        (VERIFIED, _(VERIFIED)))
    verification_status = models.CharField(
        _("Verification Status"), max_length=128,
        choices=VERIFICATION_STATUS_CHOICES,
        default=VERIFICATION_STATUS_CHOICES[0][0],
        db_index=True)
    date_created = models.DateTimeField(
        _("Date Created"), auto_now_add=True)
    date_updated = models.DateTimeField(
        _("Date Updated"), auto_now=True)

    def verification_required(self):
        return self.verification_status == self.UNVERIFIED

    def verification_failed(self):
        return self.verification_status == self.VERIFICATION_FAILED

    def verification_started(self):
        return self.verification_status != self.UNVERIFIED

    def authentication_documents_required(self):
        return self.verification_status in [
            self.UNVERIFIED, self.WAITING_FOR_MORE_DOCUMENTS]

    class Meta:
        abstract = True

class AuthenticationDocument(models.Model):
    """
    A shipping label image of a product
    """
    original = models.FileField(
        _("Document"), upload_to=settings.PACKAGE_RECEIVER_DOCUMENT_FOLDER)
    caption = models.CharField(
        _("Caption"), max_length=200, blank=True, null=True)
    ID, DRIVER_LICENSE, PASSPORT, OTHER = (
        "National Identify Card",
        "Driver's License",
        "Passport",
        "Other")
    CATEGORY_STATUS_CHOICES = (
        (ID, _(ID)),
        (DRIVER_LICENSE, _(DRIVER_LICENSE)),
        (PASSPORT, _(PASSPORT)),
        (OTHER, _("Other (must include photo)")))
    category = models.CharField(
        _("Document Category"), max_length=128,
        choices=CATEGORY_STATUS_CHOICES, )
    date_created = models.DateTimeField(
        _("Date Created"), auto_now_add=True)

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

    def filename(self):
        return os.path.basename(self.original.name)

    class Meta:
        abstract = True
        verbose_name = _('Authentication Document')
        verbose_name_plural = _('Authentication Documents')