from oscar.apps.checkout.forms import ShippingAddressForm as CoreShippingAddressForm
from django import forms
from django.utils.translation import ugettext_lazy as _
from apps.catalogue.models import ProductCustomsForm, CustomsFormItem
from apps.order.models import ShippingLabel
from django.db.models import get_model
from django.conf import settings
from decimal import Decimal as D
from oscar.apps.address.models import Country
from apps.shipping_calculator import utils
from apps.address.forms import US_STATES
from apps.address.validators import alphanumeric_and_numbers, AddressValidators

ShippingAddress = get_model('order', 'ShippingAddress')


class ShippingCustomForm(forms.ModelForm):
    def __init__(self, package, num_of_items, is_readonly, missing_value, *args, **kwargs):
        include_hs_tariff_number_fields = kwargs.pop('include_hs_tariff_number_fields', False)
        super(ShippingCustomForm, self).__init__(*args, **kwargs)
        attrs = {'autocomplete': 'off'}
        self.num_of_items = num_of_items
        self.package = package
        self.is_readonly = is_readonly
        self.missing_value = missing_value

        if is_readonly:
            self.fields['content_type'].widget.attrs['readonly'] = ''
            attrs['readonly'] = ''

        required = True
        for i in range(self.num_of_items):
            self.fields['content_' + 'desc%s' % i] = forms.CharField(
                max_length=128, label=_("Item #%s detailed description" % (i + 1)),
                validators=[alphanumeric_and_numbers], required=required,
                widget=forms.TextInput(attrs=attrs))
            self.fields['content_' + 'quantity%s' % i] = forms.IntegerField(
                label=_("Item #%s quantity" % (i + 1)), min_value=1, required=required,
                max_value=999, widget=forms.TextInput(attrs=attrs))
            self.fields['content_' + 'value%s' % i] = forms.DecimalField(
                max_digits=6, decimal_places=2, label=_("Item #%s total value" % (i + 1)),
                help_text='item value x quantity', min_value=D('1.00'), required=required,
                widget=forms.TextInput(attrs=attrs))
            if include_hs_tariff_number_fields:
                self.fields['content_' + 'hs_number%s' % i] = forms.CharField(
                max_length=6, label=_("Item #%s harmonized system for tariffs number" % (i + 1)),
                required=False, widget=forms.TextInput(attrs=attrs))
            required = False

    def clean(self):
        cleaned_data = super(ShippingCustomForm, self).clean()
        if not self._errors:
            max_value = D(getattr(settings, 'MAX_CONTENTS_VALUE', '2499.99'))
            found_item_value_above_max = False
            total_value = D('0.0')

            #check that there is no missing data only when form is valid
            #we are expecting to get data in 3 (except for content type)

            for i in range(self.num_of_items):
                category_desc = cleaned_data.get('content_desc%s' % i)
                category_value = cleaned_data.get('content_value%s' % i)
                category_quantity = cleaned_data.get('content_quantity%s' % i)

                filter_list = [category_desc, category_value, category_quantity]
                if any(filter_list) and not all(filter_list):
                    raise forms.ValidationError(_("Missing data found, Please complete the form"))

                if any(filter_list):
                    total_value += category_value
                    ret = utils.usps_validate_package_value(category_value)
                    if ret:
                        found_item_value_above_max = True
                        field_name = 'content_value%s' % i
                        self._errors[field_name] = self.error_class([ret['msg']])
                        #del cleaned_data[field_name]

            if not found_item_value_above_max and total_value > max_value:
                raise forms.ValidationError(_("Contents value must not exceed $%s."
                                              " Please contact customer support to get your items delivered" % max_value))

        return cleaned_data

    def save(self, commit=True):
        #don't save anything when is_readonly flag is set
        #this is a case when we already filled the customs form declaration for the customer
        #in such case no change to the declaration is allowed
        if self.is_readonly and not self.missing_value:
            return None
        #package can only have 1 customs form
        #create one only if it does not exist
        try:
            obj = self.package.customs_form
        except ProductCustomsForm.DoesNotExist:
            obj = super(ShippingCustomForm, self).save(commit=False)
            obj.package = self.package
        else:
            obj.content_type = self.cleaned_data['content_type']
        obj.save()
        customs_form_items_data = []
        for i in range(self.num_of_items):
            desc = self.cleaned_data['content_' + 'desc%s' % i]
            quantity = self.cleaned_data['content_' + 'quantity%s' % i]
            value = self.cleaned_data['content_' + 'value%s' % i]
            hs_tariff_number = self.cleaned_data.get('content_' + 'hs_number%s' % i)

            if desc and quantity and value:
                customs_form_items_data.append({
                    'description': desc,
                    'quantity': quantity,
                    'value': value,
                    'hs_tariff_number': hs_tariff_number,
                    'customs_form': obj
                })
        #remove all customs from items to be cleaned
        obj.remove_items()
        #create objects
        customs_form_items_objs = [CustomsFormItem(**vals) for vals in customs_form_items_data]
        #save all to db
        CustomsFormItem.objects.bulk_create(customs_form_items_objs)
        return obj

    class Meta:
        model = ProductCustomsForm
        exclude = ('items', 'date_created', 'package')


class ShippingAddressForm(CoreShippingAddressForm, AddressValidators):
    def __init__(self, *args, **kwargs):
        is_business_account = kwargs.pop('is_business_account', False)
        super(ShippingAddressForm,self ).__init__(*args, **kwargs)
        if 'phone_number' in self.fields:
            self.fields['phone_number'].help_text = ''
            self.fields['phone_number'].required = True
        #Include US as shipping country for business account
        if is_business_account:
            self.fields['country'].queryset |= Country.objects.filter(iso_3166_1_a2='US')
        self.add_validators(self.fields)

    class Meta:
        model = ShippingAddress
        exclude = ('user', 'search_text', 'title', 'notes', )


class ReturnToStoreShippingAddressForm(ShippingAddressForm):
    def __init__(self, merchant_name, *args, **kwargs):
        super(ReturnToStoreShippingAddressForm, self ).__init__(*args, **kwargs)
        if 'first_name' in self.fields:
            self.fields['first_name'].label = _("Merchant name")
            self.fields['first_name'].validators = [alphanumeric_and_numbers]
        if 'state' in self.fields:
            self.fields['state'].required = True
        if 'phone_number' in self.fields:
            self.fields['phone_number'].required = False
        if 'postcode' in self.fields:
            self.fields['postcode'].required = True
        #return to merchant country is always US
        del self.fields['country']
        self.country_us = Country.objects.get(iso_3166_1_a2='US')
        self.instance.country = self.country_us
        self.merchant_name = merchant_name

    def save(self, commit=True):
        address = super(ReturnToStoreShippingAddressForm, self).save(commit=False)
        #use default values for country and merchant name
        address.country = self.country_us
        #use first name as merchant name
        address.first_name = self.merchant_name + ' RETURN ADDRESS'
        address.save()
        return address


    class Meta:
        model = ShippingAddress
        widgets = {
            'state': forms.Select(choices=US_STATES),
            'first_name': forms.TextInput(attrs={'readonly': 'readonly'})
        }
        exclude = ('user', 'search_text', 'title', 'last_name')


class ReturnToStoreContentValueForm(forms.Form):
    total_value = forms.DecimalField(
        max_digits=6, decimal_places=2, label=_("Total Value"),
        help_text=_("Enter the total value of package's content"),
        widget=forms.TextInput(attrs={'autocomplete': 'off'})
    )

    def clean_total_value(self):
        """
        enforce max and min content value applied by USPS
        """
        total_value = self.cleaned_data.get('total_value')
        ret = utils.usps_validate_package_value(total_value)
        if ret:
            raise forms.ValidationError(ret['msg'])
        return total_value


class ReturnToStorePrepaidLabelForm(forms.ModelForm):
    IMAGE_MAX_FILE_SIZE = 5 * 1024 *1024 #5MB

    def __init__(self, *args, **kwargs):
        super(ReturnToStorePrepaidLabelForm, self).__init__(*args, **kwargs)
        self.fields['original'].required = False
        self.fields['original'].label = _("Return label")

    def clean(self):
        cleaned_data = super(ReturnToStorePrepaidLabelForm, self).clean()
        if not self._errors:
            uploaded_shipping_label = cleaned_data.get('original')
            if not uploaded_shipping_label:
                raise forms.ValidationError(_("You have not selected a return label"))
            #check for file size
            if uploaded_shipping_label.size > self.IMAGE_MAX_FILE_SIZE:
                raise forms.ValidationError(_("Return label file is too large, ( > 5MB )"))
        return cleaned_data

    class Meta:
        model = ShippingLabel
        exclude = ('order', 'date_created', 'caption')








