from apps.user.uuid import generate_uuid
from oscar.apps.dashboard.catalogue.forms import ProductCategoryForm\
    ,BaseProductCategoryFormSet as CoreBaseProductCategoryFormSet, ProductForm as CoreProductForm
from django.db.models import get_model
from django.contrib.auth.models import User
from apps.catalogue.utils import generate_upc, process_consolidated_package_predefined_special_request
from apps.user.models import Profile
from apps.catalogue.models import (
    ProductCustomsForm, CustomsFormItem,
    ProductSpecialRequests, ProductConsolidationRequests,
    ProductPackagingImage, AdditionalPackageReceiver,
    PackageLocation)
from oscar.forms.widgets import ImageInput
from django import forms
from django.forms.models import inlineformset_factory, BaseInlineFormSet
from django.forms.formsets import formset_factory, BaseFormSet
from apps.address.validators import alphanumeric_and_numbers
from django.conf import settings
from decimal import Decimal as D
from django.utils.translation import ugettext_lazy as _
from apps.shipping_calculator import utils
from oscar.core.loading import get_class
from apps.partner.utils import create_package_stock_record
from PIL import Image
import string


ProductCategory = get_model('catalogue', 'ProductCategory')
Product = get_model('catalogue', 'Product')
ProductImage = get_model('catalogue', 'ProductImage')
CoreProductImageForm = get_class('dashboard.catalogue.forms', 'ProductImageForm')
UserSelect = get_class('dashboard.users.widgets', 'UserSelect')

class ProductImageResizer(object):
     def resize_product_image(self, file_path, width, height):
        """
        We need to keep fixed size for photos that the operational stuff upload
        """
        image = Image.open(file_path)
        image.thumbnail((width, height), Image.ANTIALIAS)
        image.save(file_path)

class UserModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        try:
            profile = obj.get_profile()
        except Profile.DoesNotExist:
            profile = Profile(user=obj)
            profile.uuid = generate_uuid()
            profile.save()

        return unicode(profile.uuid)


class BaseProductCategoryFormSet(CoreBaseProductCategoryFormSet):
    def clean(self):
        return

ProductCategoryFormSet = inlineformset_factory(
    Product, ProductCategory, form=ProductCategoryForm,
    formset=BaseProductCategoryFormSet, fields=('category',), extra=1,
    can_delete=False)


class ProductForm(CoreProductForm):
    too_rigid = forms.CharField(required=False, widget=forms.HiddenInput())
    not_rectangular = forms.CharField(required=False, widget=forms.HiddenInput())
    thickness_variations = forms.CharField(required=False, widget=forms.HiddenInput())
    YES, NO = True, False
    YES_NO = ((YES, _('Yes')),
              (NO, _('No')))
    is_name_matched = forms.NullBooleanField(
        label=_("Shipping address name matches account holder name?"),
        #initial=True,
        widget=forms.RadioSelect(choices=YES_NO))
    prohibited_items_msg = forms.CharField(
        label=_("Prohibited items description - this will be sent to the customer"),
        max_length=128, required=False
    )

    PENDING, PREDEFINED_WAITING_FOR_CONSOLIDATION,\
    WAITING_FOR_CONSOLIDATION, PAID, CONSOLIDATION_TAKING_PLACE,\
    CONSOLIDATION_DONE, HANDLING_SPECIAL_REQUESTS,\
    HANDLING_SPECIAL_REQUESTS_DONE, SHIPPED, SETTLED,\
    PREDEFINED_PACKED, PACKED,\
    POSTAGE_PURCHASED, POSTAGE_MISMATCH, \
    RETURNED_TO_SENDER, DISCARDED,\
    CONTAINS_PROHIBITED_ITEMS, PENDING_RETURNED_PACKAGE,\
    PRE_PENDING, LOST_IN_WAREHOUSE, PENDING_CLEARANCE = (
        'pending', 'predefined_waiting_for_consolidation',
        'waiting_for_consolidation', 'paid', 'consolidation_taking_place',
        'consolidation_done', 'handling_special_requests',
        'handling_special_requests_done', 'shipped', 'settled',
        'predefined_packed', 'packed',
        'postage_purchased', 'postage_mismatch',
        'returned_to_sender', 'discarded',
        'contains_prohibited_items', 'pending_returned_package',
        'pre_pending', 'lost_in_warehouse', 'pending_clearance'
    )
    STATUS_CHOICES = (
        ('', '-------------'),
        (PENDING, _('Pending')),
        (PRE_PENDING, _('Pre pending')),
        (PREDEFINED_WAITING_FOR_CONSOLIDATION, _('Predefined waiting for consolidation')),
        (WAITING_FOR_CONSOLIDATION, _('Waiting for consolidation')),
        (PAID, _('Paid')),
        (CONSOLIDATION_TAKING_PLACE, _('Consolidation taking place')),
        (CONSOLIDATION_DONE, _('Consolidation done')),
        (HANDLING_SPECIAL_REQUESTS, _('Handling extra services')),
        (HANDLING_SPECIAL_REQUESTS_DONE, _('Handling extra services done')),
        (SHIPPED, _('Shipped')),
        (SETTLED, _('Settled')),
        (PREDEFINED_PACKED, _('Predefined packed')),
        (PACKED, _('Packed')),
        (POSTAGE_PURCHASED, _('Postage purchased')),
        (POSTAGE_MISMATCH, _('Postage mismatch')),
        (RETURNED_TO_SENDER, _('Returned to sender')),
        (DISCARDED, _('Discarded')),
        (CONTAINS_PROHIBITED_ITEMS, _('Contains prohibited items')),
        (PENDING_RETURNED_PACKAGE, _('Returned package')),
        (LOST_IN_WAREHOUSE, _('Lost in warehouse')),
        (PENDING_CLEARANCE, _('Pending payment clearance')),
    )
    NEEDED_FIELDS = [
        'upc', 'owner', 'title', 'condition', 'status',
        'is_client_id_missing', 'combined_products', 'is_name_matched',
        'too_rigid', 'not_rectangular', 'thickness_variations',
        'is_contain_prohibited_items', 'prohibited_items_msg',
        'is_sent_outside_usa', 'battery_status', 'merchant_zipcode'
    ]
    STAFF_FIELDS = ['status']

    def __init__(self, product_class, *args, **kwargs):
        is_staff = kwargs.pop('is_staff', False)
        #generate upc only for new products
        instance = kwargs.get('instance')
        if not instance:
            self.set_initial_upc_value(kwargs)
        super(ProductForm, self).__init__(product_class, *args, **kwargs)
        self.fields['owner'] = UserModelChoiceField(
            label='Customer ID (suite number) or name',
            required=True,
            queryset=User.objects.filter(profile__isnull=False, is_staff=False),
            widget=UserSelect(attrs={'data-action': 'predefined_special_requests'}))
        self.fields['upc'].widget.attrs['readonly'] = 'readonly'
        self.fields['upc'].label = 'Package ID'
        self.fields['upc'].help_text = ''
        self.fields['condition'].required = True
        self.fields['title'].required = True
        self.fields['title'].label = 'Merchant name'
        self.fields['merchant_zipcode'].required = True
        self.fields['is_client_id_missing'].required = True
        self.fields['is_sent_outside_usa'].required = True
        self.fields['battery_status'].required = True
        self.fields['is_contain_prohibited_items'].required = True

        #show only relevant fields + all product attributes
        for key in self.fields.keys():
            if key not in self.NEEDED_FIELDS and not key.startswith('attr_'):
                self.fields.pop(key)

        #show only combined_products for consolidated packages
        if not instance or not instance.is_consolidated:
            self.fields.pop('combined_products')
        else:
            #show only packages
            self.fields['combined_products'].queryset = instance.combined_products.all()

        #additional receiver is only applicable for new package intake
        #show status only when edit a product
        if instance:
            self.fields.pop('is_name_matched')
            self.fields['status'] = forms.ChoiceField(
                choices=self.STATUS_CHOICES,
                initial=instance.status if instance else None,
                required=False)
        else:
           self.fields.pop('status')

        #if user isn't staff remove staff only fields
        #if not is_staff:
        #    for field in self.STAFF_FIELDS:
        #        self.fields.pop(field)
        #staff only fields, currently we only have 1 such field
        #else:

        try:
            #enforce this order LxWxH Weight
            length = self.fields.pop('attr_length')
            width = self.fields.pop('attr_width')
            height = self.fields.pop('attr_height')
            weight = self.fields.pop('attr_weight')
            prohibited_items_msg = self.fields.pop('prohibited_items_msg')
            self.fields.insert(6, 'prohibited_items_msg', prohibited_items_msg)
            self.fields.insert(-1, 'attr_length', length)
            self.fields.insert(-1, 'attr_width', width)
            self.fields.insert(-1, 'attr_height', height)
            self.fields.insert(-1, 'attr_weight', weight)
            #wrap is_envelope field to enforce the user to make a selection and make it show first
            self.fields.pop('attr_is_envelope')
            self.fields.insert(0, 'attr_is_envelope', forms.NullBooleanField(label=_("envelope?"),
                                                      widget=forms.RadioSelect(choices=self.YES_NO)))
        #only packages have the above attributes
        except KeyError:
            pass

    @staticmethod
    def make_bool(str):
        if str and str.lower() == 'true':
            return True
        return False

    def set_initial_upc_value(self, kwargs):
        kwargs['initial']['upc'] = generate_upc()

    #def clean_attr_weight(self):
    #    #validate that the weight of consolidated package is not exceeding the max weight per destination
    #    #since we don't want to split the consolidated package into smaller
    #    #packages we need to make sure it can be shipped via USPS to any country
    #    #We got some max weights for selected countries, if we can't find the country we use
    #    #default max_weight of 44 which should be fine with all countries
    #    #we take the owner country to determine the shipping destination - this should answer 99.99%
    #    #of the cases
    #    weight = self.cleaned_data.get('attr_weight')
    #    if self.instance.id and\
    #       self.instance.is_consolidated:
    #        owner_profile = self.instance.owner.get_profile()
    #        owner_country = owner_profile.country
    #        owner_proxy_score = owner_profile.proxy_score
    #        max_weight = settings.CONSOLIDATED_PACKAGE_MAX_WEIGHT['DEFAULT']
    #        if owner_proxy_score is not None and owner_proxy_score == 0: #user is not behind a proxy, we can take his country into account
    #            max_weight = settings.CONSOLIDATED_PACKAGE_MAX_WEIGHT.get(owner_country, max_weight)
    #        if weight > max_weight:
    #            raise forms.ValidationError(_("Max weight of consolidated package must not exceed %d lbs, please contact"
    #                                          " manager before continuing.") % max_weight)
    #    return weight

    def clean_attr_is_envelope(self):
        is_envelope = self.cleaned_data.get('attr_is_envelope')
        if is_envelope is None:
            raise forms.ValidationError(_("This field is required"))
        return is_envelope

    def clean_is_client_id_missing(self):
        is_client_id_missing = self.cleaned_data.get('is_client_id_missing')
        if is_client_id_missing is None:
            raise forms.ValidationError(_("This field is required"))
        return is_client_id_missing

    def clean_is_sent_outside_usa(self):
        is_sent_outside_usa = self.cleaned_data.get('is_sent_outside_usa')
        if is_sent_outside_usa is None:
            raise forms.ValidationError(_("This field is required"))
        return is_sent_outside_usa

    def clean_is_contain_prohibited_items(self):
        is_contain_prohibited_items = self.cleaned_data.get('is_contain_prohibited_items')
        if is_contain_prohibited_items is None:
            raise forms.ValidationError(_("This field is required"))
        return is_contain_prohibited_items

    def clean_is_name_matched(self):
        is_name_matched = self.cleaned_data.get('is_name_matched')
        if is_name_matched is None:
            raise forms.ValidationError(_("This field is required"))
        return is_name_matched

    def check_envelope_limitations(self):
        envelope_limitations = [
            self.make_bool(self.cleaned_data.get('too_rigid')),
            self.make_bool(self.cleaned_data.get('not_rectangular')),
            self.make_bool(self.cleaned_data.get('thickness_variations'))
        ]
        #check if envelope passed USPS limitations
        if any(envelope_limitations) or \
           self.cleaned_data.get('attr_weight', 0.0) > settings.USPS_MAX_ENVELOPE_WEIGHT:
            self.cleaned_data['attr_is_envelope'] = False

    def clean(self):
        """
        Fixed oscar's bug where submitting the product form with no title
        """
        data = self.cleaned_data
        if 'parent' not in data and not data.get('title'):
            raise forms.ValidationError(_("This field is required"))
        elif 'parent' in data and data['parent'] is None and not data['title']:
            raise forms.ValidationError(_("Parent products must have a title"))
        #change is_envelope value to False if envelope failed any limitation
        self.check_envelope_limitations()
        return super(ProductForm, self).clean()

    def save(self):
        """
        We modified the package creating view to show only relevant attributes
        therefore not all attributes exist on form so we need to wrap it up with
        KeyError exception handling to bypass the missing attributes
        """
        object = super(CoreProductForm, self).save(commit=False)
        object.product_class = self.product_class
        #make sure merchant name is capitalized
        object.title = string.capwords(object.title)

        is_populated = False
        for attribute in self.product_class.attributes.all():
            try:
                value = self.cleaned_data['attr_%s' % attribute.code]
            except KeyError:
                continue
            else:
                if not is_populated:
                    #FIX oscar bug: populate product attributes before changing their values
                    try:
                        getattr(object.attr, attribute.code)
                    except AttributeError:
                        pass
                    is_populated = True
                setattr(object.attr, attribute.code, value)

        if not object.upc:
            object.upc = None

        object.save()
        self.save_m2m()
        return object

    class Meta:
        YES, NO = True, False
        YES_NO = ((YES, _('Yes')),
                  (NO, _('No')))
        model = Product
        fields = [
            'upc', 'title', 'merchant_zipcode', 'parent', 'owner',
            'status', 'condition', 'is_client_id_missing',
            'combined_products', 'is_contain_prohibited_items',
            'is_sent_outside_usa', 'battery_status']
        widgets = {
            'is_client_id_missing': forms.RadioSelect(choices=YES_NO),
            'is_sent_outside_usa': forms.RadioSelect(choices=YES_NO),
            'is_contain_prohibited_items': forms.RadioSelect(choices=YES_NO),
        }


class ProductPackagingImageForm(forms.ModelForm, ProductImageResizer):
    class Meta:
        model = ProductPackagingImage
        exclude = ('caption', 'display_order')
        # use ImageInput widget to create HTML displaying the
        # actual uploaded image and providing the upload dialog
        # when clicking on the actual image.
        widgets = {
            'original': ImageInput(),
        }

class FirstFormRequiredFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super(FirstFormRequiredFormSet, self).__init__(*args, **kwargs)
        self.forms[0].empty_permitted = False

ProductPackagingImageFormSet = inlineformset_factory(
    Product, ProductPackagingImage, form=ProductPackagingImageForm,
    formset=FirstFormRequiredFormSet, extra=5)

class CustomsFormItemForm(forms.ModelForm):
    REQUIRED_FIELDS = ['description', 'quantity', 'value']

    def __init__(self, *args, **kwargs):
        super(CustomsFormItemForm, self).__init__(*args, **kwargs)
        if 'description' in self.fields:
            self.fields['description'].validators = [alphanumeric_and_numbers]

    def clean(self):
        cleaned_data = super(CustomsFormItemForm, self).clean()

        if not any(self.errors):
            category_value = cleaned_data.get('value')
            is_delete = cleaned_data.get('DELETE', False)
            if not is_delete and category_value:
                ret = utils.usps_validate_package_value(category_value)
                if ret:
                    self._errors['value'] = self.error_class([ret['msg']])
                    del cleaned_data['value']

        return cleaned_data

    class Meta:
        model = CustomsFormItem


class BaseCustomsFormItemFormSet(BaseInlineFormSet):
    def count_submitted_forms(self):
        count = 0
        for form in self.forms:
            try:
                if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                    count += 1
            except AttributeError:
                pass
        return count

    def clean(self):
        cleaned_data = super(BaseCustomsFormItemFormSet, self).clean()
        if not any(self.errors):
            total_value = D('0.0')
            max_value = D(getattr(settings, 'MAX_CONTENTS_VALUE', '2499.99'))
            submitted_forms = self.count_submitted_forms()
            if not self.instance or not self.instance.content_type and submitted_forms:
                raise forms.ValidationError(_("Package content type must be filled."))
            if self.instance and self.instance.content_type and not submitted_forms:
                raise forms.ValidationError(_("Customs form requires at least 1 declared item."))
            for form in self.forms:
                    value = form.cleaned_data.get('value')
                    is_delete = form.cleaned_data.get('DELETE', False)
                    if not is_delete and value:
                        total_value += value

            if total_value > max_value:
                raise forms.ValidationError(_("Package content total value must not exceed $%s." % max_value))
        return cleaned_data


CustomsFormItemFormSet = inlineformset_factory(
    ProductCustomsForm, CustomsFormItem, form=CustomsFormItemForm,
    formset=BaseCustomsFormItemFormSet, fields=('description', 'quantity', 'value'),
    extra=5)

class ProductImageForm(CoreProductImageForm, ProductImageResizer):
    def save(self, *args, **kwargs):
        # We infer the display order of the image based on the order of the
        # image fields within the formset.
        kwargs['commit'] = False
        obj = super(ProductImageForm, self).save(*args, **kwargs)
        obj.display_order = self.get_display_order()
        if obj.original:
            #resize uploaded photos to 540px - 540px
            self.resize_product_image(obj.original.path, 1000, 720)
        obj.save()
        return obj


ProductImageFormSet = inlineformset_factory(
    Product, ProductImage, form=ProductImageForm, extra=5)


class CustomsDeclarationForm(forms.ModelForm):
    class Meta:
        model = ProductCustomsForm
        exclude = ('package', )


class SpecialRequestForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        is_superuser = kwargs.pop('is_superuser', False)
        super(SpecialRequestForm, self).__init__(*args, **kwargs)
        if (self.instance or kwargs.get('data')) and not is_superuser:
            visible_fields = []
            if self.instance.is_custom_requests or (kwargs.get('data') and kwargs['data'].get('is_custom_requests')):
                visible_fields.extend(['is_custom_requests', 'custom_requests_done', 'custom_requests_details'])
            if self.instance.is_repackaging or (kwargs.get('data') and kwargs['data'].get('is_repackaging')):
                visible_fields.append('repackaging_done')
            if self.instance.is_remove_invoice or (kwargs.get('data') and kwargs['data'].get('is_remove_invoice')):
                visible_fields.append('remove_invoice_done')
            if self.instance.is_extra_protection or (kwargs.get('data') and kwargs['data'].get('is_extra_protection')):
                visible_fields.append('extra_protection_done')
            for field_name, field in self.fields.iteritems():
                if field_name not in visible_fields:
                    field.widget = forms.HiddenInput()
        self.fields['is_photos'].required = False

    class Meta:
        YES, NO = True, False
        YES_NO = ((YES, _('Yes')),
                  (NO, _('No')))
        model = ProductSpecialRequests
        exclude = ('package', )
        widgets = {
            'repackaging_done': forms.RadioSelect(choices=YES_NO),
            'custom_requests_done': forms.RadioSelect(choices=YES_NO),
            'remove_invoice_done': forms.RadioSelect(choices=YES_NO),
            'extra_protection_done': forms.RadioSelect(choices=YES_NO)
        }

    def clean_custom_requests_details(self):
        """
        Make sure that custom requests details field was filled if
        custom requests succeeded
        """
        custom_requests_done = self.cleaned_data.get('custom_requests_done')
        custom_requests_details = self.cleaned_data.get('custom_requests_details')
        if custom_requests_done and not custom_requests_details:
            raise forms.ValidationError(_("No detailed summary on the action we've taken on the items."))
        return custom_requests_details


class ConsolidationRequestForm(forms.ModelForm):
    class Meta:
        model = ProductConsolidationRequests
        exclude = ('package', )


class PredefinedParcelsForm(forms.Form):
    EM, PEN, LEN, XS, SM, MD, LR = ('EM', 'PEN', 'LEN', 'XS', 'SM', 'MD', 'LR')
    PARCEL_CHOICES = (
        (EM, "-----------"),
        #(PEN, _("USPS Padded Envelope")),
        #(LEN, _("USPS Legal Envelope")),
        (XS, _("Extra Small Box")),
        (SM, _("Small box")),
        (MD, _("Medium box")),
        (LR, _("Large box"))
    )
    predefined_parcels = forms.ChoiceField(
        label=_("Predefined parcels"),
        required=False, choices=PARCEL_CHOICES,
        widget=forms.Select(attrs={'data-action': 'predefined_parcels'})
    )


class DamagedPackageForm(forms.Form):
    owner = UserModelChoiceField(label=_('Owner'),
                                 required=True,
                                 queryset=User.objects.filter(profile__isnull=False, is_staff=False),
                                 widget=UserSelect())
    merchant_name = forms.CharField(label=_('Merchant name'),
                                    max_length=128,
                                    required=True)


class ReturnedPackageForm(forms.Form):
    PERFECT, SLIGHTLY_DAMAGED, DAMAGED = ("Perfect", "Slightly Damaged", "Damaged")
    UNKNOWN, BATTERY = ("Unknown", "Battery")
    NO_BATTERY, INSTALLED_BATTERY, LOOSE_BATTERY = (
        "No Battery", "Installed Battery", "Loose Battery"
    )
    BATTERY_CHOICES = (
        (NO_BATTERY, _(NO_BATTERY)),
        (INSTALLED_BATTERY, _(INSTALLED_BATTERY)),
        (LOOSE_BATTERY, _(LOOSE_BATTERY))
    )
    CONDITION_CHOICES = (
        ('', '--------'),
        (PERFECT, _(PERFECT)),
        (SLIGHTLY_DAMAGED, _(SLIGHTLY_DAMAGED)),
        (DAMAGED, _(DAMAGED))
    )
    RETURN_REASON_CHOICES = (
        (UNKNOWN, _(UNKNOWN)),
        (BATTERY, _("Package contains battery"))
    )
    owner = UserModelChoiceField(label=_('Owner'),
                                 required=True,
                                 queryset=User.objects.filter(profile__isnull=False, is_staff=False),
                                 widget=UserSelect())
    package_upc = forms.CharField(label=_('Package ID'),
                                  max_length=64,
                                  required=True)
    condition = forms.ChoiceField(
        choices=CONDITION_CHOICES,
        label=_("Parcel Condition"), required=True)
    reason = forms.ChoiceField(
        choices=RETURN_REASON_CHOICES,
        label=_("Return Reason"), required=True)
    battery_status = forms.ChoiceField(
        choices=BATTERY_CHOICES,
        label=_("Battery Status?"), required=True)

    def clean(self):
        #we must make sure both owner and package_id were filled
        #we validate this if and only if at least 1 of them submitted
        cleaned_data = super(ReturnedPackageForm, self).clean()
        owner = cleaned_data.get('owner')
        upc = cleaned_data.get('package_upc')

        #make sure the package belongs to the customer
        if owner and upc:
            try:
                package = Product.objects.get(upc=upc, owner=owner)
            except Product.DoesNotExist:
                raise forms.ValidationError(_("Package does not belong to customer"))
            else:
                #check that the package has already been shipped
                #for cases where the package has not been shipped but returned due some errors
                #we need to refund the label and purchase a new label
                if package.status.lower() != 'shipped':
                    raise forms.ValidationError(_("Package wasn't shipped, please contact manager."))
        return cleaned_data


class EnvelopeRestrictionsForm(forms.Form):
    too_rigid = forms.BooleanField(label=_("The Large Envelope is too Rigid, does not bend easily"),
                                   required=False)
    not_rectangular = forms.BooleanField(label=_("The Large Envelope is NOT Rectangular or Square"),
                                         required=False)
    thickness_variations = forms.BooleanField(label=_("The Large Envelope contains items that cause more than"
                                                   " 1/4 inch variation in thickness"),
                                              required=False)


class AdditionalPackageReceiverForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super(AdditionalPackageReceiverForm, self).clean()
        if not any(self.errors):
            if 'first_name' in cleaned_data:
                cleaned_data['first_name'] = cleaned_data['first_name'].strip()
            if 'last_name' in cleaned_data:
                cleaned_data['last_name'] = cleaned_data['last_name'].strip()
        return cleaned_data

    def save(self, *args, **kwargs):
        """
        We need to make sure we keep only 1 additional package receiver
        for all packages with the same receiver.
        So we first try to load the receiver from the DB using the first and
        last names, if it doesn't exist we save it, otherwise, we do nothing
        """
        package_owner = kwargs.pop('package_owner')
        try:
            additional_receiver = AdditionalPackageReceiver.objects.get(
                package_owner=package_owner,
                first_name__iexact=self.cleaned_data.get('first_name', ''),
                last_name__iexact=self.cleaned_data.get('last_name', ''))
        except AdditionalPackageReceiver.DoesNotExist:
            additional_receiver = self.instance
            additional_receiver.package_owner = package_owner
            #for business account change additional receiver status to verified
            if package_owner and package_owner.get_profile().account_type == Profile.BUSINESS:
                additional_receiver.verification_status = AdditionalPackageReceiver.VERIFIED
            return super(AdditionalPackageReceiverForm, self).save(*args, **kwargs)
        return additional_receiver


    class Meta:
        model = AdditionalPackageReceiver
        fields = ('first_name', 'last_name')

class ExtraConsolidationPackagesForm(forms.Form):
    def __init__(self, packages, *args, **kwargs):
        super(ExtraConsolidationPackagesForm, self).__init__(*args, **kwargs)
        self.fields['extra_consolidation_package'] = forms.MultipleChoiceField(
            label=_("Extra consolidation package"),
            choices=[(p.id, p.upc) for p in packages],
            required=False)
        self.packages = packages

    def get_package(self, pk):
        return filter(lambda x: x.pk == int(pk), self.packages)

    def get_combined_packages(self):
        packages_ids = map(int, self.cleaned_data.get('extra_consolidation_package', []))
        return filter(lambda x: x.pk in packages_ids, self.packages)

    def dup_consolidated_package(self, org_package, children):
        #fork org_package to enter a new package into the system for the returned package
        #we don't duplicate extra services and variants as all fees will be collected
        #only once for the original consolidated box - not on the extra boxes
        extra_consolidated_package = Product(
            upc=generate_upc(),
            condition='Perfect',
            status='consolidation_taking_place',
            is_client_id_missing=False,
            is_discountable=org_package.is_discountable,
            product_class=org_package.product_class,
            owner=org_package.owner,
            title=org_package.create_consolidated_package_title(children),
            date_consolidated=org_package.date_consolidated
        )
        setattr(extra_consolidated_package.attr, 'weight', 0.0)
        setattr(extra_consolidated_package.attr, 'height', 0.0)
        setattr(extra_consolidated_package.attr, 'width',  0.0)
        setattr(extra_consolidated_package.attr, 'length', 0.0)
        setattr(extra_consolidated_package.attr, 'is_envelope', False)

        #save package to DB
        extra_consolidated_package.save()

        #Take partner from children list and create a stockrecord for large package
        partner = children[0].partner
        create_package_stock_record(package=extra_consolidated_package, partner=partner)

        #process predefined extra services
        process_consolidated_package_predefined_special_request(extra_consolidated_package)

        #add new combined packages
        extra_consolidated_package.combined_products.add(*children)

        #need to update the date_create field of the new consolidated box
        #we must do it only after we save the object into the DB
        extra_consolidated_package.date_created = extra_consolidated_package.calculate_date_created(children)
        extra_consolidated_package.save()

        ProductConsolidationRequests.objects.create(
            package=extra_consolidated_package,
            item_packing=org_package.consolidation_requests.item_packing,
            container=org_package.consolidation_requests.container
        )

    def process_extra_consolidation_box(self, original_consolidated_package, **kwargs):
        children = self.get_combined_packages()
        #if the extra box only contains 1 package, no new consolidation is needed
        #we just change the status back to pending
        if len(children) == 1:
            child = children[0]
            child.status='pending'
            child.save()
        elif len(children) > 1:
            self.dup_consolidated_package(original_consolidated_package, children)

class ExtraConsolidationPackagesBaseFormSet(BaseFormSet):
    def __init__(self, packages, *args, **kwargs):
        self.packages = packages
        self.current_combined_packages_id = kwargs.pop('current_combined_packages_id', [])
        super(ExtraConsolidationPackagesBaseFormSet, self).__init__(*args, **kwargs)
        for form in self.forms:
            form.empty_permitted = True

    def _construct_forms(self):
        self.forms = []
        for i in xrange(self.total_form_count()):
            self.forms.append(self._construct_form(i, packages=self.packages))

    def clean(self):
        cleaned_data = super(ExtraConsolidationPackagesBaseFormSet, self).clean()
        if not any(self.errors):
            combined_packages_id = []
            for form in self.forms:
                packages_id = form.cleaned_data.get('extra_consolidation_package', [])
                for package_id in packages_id:
                    if package_id in combined_packages_id:
                        package = form.get_package(package_id)
                        raise forms.ValidationError(_("Package %s can't be in 2 different boxes." % package.upc))
                    combined_packages_id.append(package_id)
            if combined_packages_id:
                all_combined_packets_ids = ["%s" % p.pk for p in self.packages]
                #first make sure that the main consolidated box has some packages inside
                if sorted(combined_packages_id, key=int) == sorted(all_combined_packets_ids, key=int):
                    raise forms.ValidationError(_("The main consolidation package has no packages inside!, all_packages = (%s)" %
                                                  ", ".join([p.upc for p in self.packages])))
                combined_packages_id.extend(self.current_combined_packages_id)
                if sorted(combined_packages_id, key=int) != sorted(all_combined_packets_ids, key=int):
                    raise forms.ValidationError(_("Not all packages included or you have duplications."
                                                  " all_packages = (%s)" % ", ".join([p.upc for p in self.packages])))
        return cleaned_data

    def process_extra_consolidation_boxes(self, original_consolidated_package):
        for form in self.forms:
            form.process_extra_consolidation_box(original_consolidated_package)

ExtraConsolidationPackagesFormSet = formset_factory(ExtraConsolidationPackagesForm,
                                                    formset=ExtraConsolidationPackagesBaseFormSet,
                                                    extra=3)

class PackageLocationForm(forms.ModelForm):
    class Meta:
        fields = ('warehouse', 'loc1', 'loc2', 'loc3')
        model = PackageLocation