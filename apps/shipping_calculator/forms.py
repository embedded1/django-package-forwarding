from django import forms
from decimal import Decimal as D
from django.utils.translation import ugettext_lazy as _
from django.db.models import get_model
from . import utils
import re


amazon_re = re.compile(r'^(http|https)://www.amazon.com+')
Country = get_model('address', 'country')

class ShippingCalculatorForm(forms.Form):
    LBS, KG, INCH, CM = 'lbs', 'kg', 'in', 'cm'
    WEIGHT_UNITS_CHOICES = (
        (LBS, 'lbs'),
        (KG, 'kg')
    )
    DIMENSION_UNITS_CHOICES = (
        (INCH, 'inch'),
        (CM, 'cm')
    )
    weight_units = forms.ChoiceField(
        label='weight_units', choices=WEIGHT_UNITS_CHOICES)
    dimension_units = forms.ChoiceField(
        label='dimension_units', choices=DIMENSION_UNITS_CHOICES)
    country = forms.ModelChoiceField(
        queryset=None, label=_("country"))
    city = forms.CharField(
        label=_("City"),
        max_length=64, required=False)
    postcode = forms.CharField(
        label=_("Post/Zip-code"),
        max_length=64, required=False)
    weight = forms.DecimalField(
        max_digits=5, decimal_places=2,
        min_value=D('0.1'), label=_("weight"),
        widget=forms.TextInput(attrs={
            'autocomplete': 'off'
        }))
    length = forms.DecimalField(
        max_digits=5, decimal_places=2,
        min_value=D('0.1'), label=_("length"),
        widget=forms.TextInput(attrs={
            'autocomplete': 'off',
            'placeholder': 'L'
        }))
    height = forms.DecimalField(
        max_digits=5, decimal_places=2,
        min_value=D('0.1'), label=_("height"),
        widget=forms.TextInput(attrs={
            'autocomplete': 'off',
            'placeholder': 'H'
        }))
    width = forms.DecimalField(
        max_digits=5, decimal_places=2,
        min_value=D('0.1'), label=_("width"),
        widget=forms.TextInput(attrs={
            'autocomplete': 'off',
            'placeholder': 'W'
        }))
    value = forms.DecimalField(
        max_digits=6, decimal_places=2,
        widget=forms.TextInput(attrs={
            'autocomplete': 'off'
        }))
    mixpanel_anon_id = forms.CharField(
        widget=forms.HiddenInput, required=False)

    def __init__(self, *args, **kwargs):
        self.set_initial_attribute_values(kwargs)
        super(ShippingCalculatorForm, self ).__init__(*args, **kwargs)
        self.set_country_queryset()

    def set_country_queryset(self):
        self.fields['country'].queryset = Country._default_manager.filter(
            is_shipping_country=True)

    def set_initial_attribute_values(self, kwargs):
        if 'initial' not in kwargs:
            kwargs['initial'] = {}

    def clean_value(self):
        """
        enforce max and min content value applied by USPS
        """
        value = self.cleaned_data.get('value')
        ret = utils.usps_validate_package_value(value)
        if ret:
            raise forms.ValidationError(ret['msg'])
        return value


class AmazonShippingCalculatorForm(forms.Form):
    country  = forms.ModelChoiceField(
        queryset=None, label=_("country"))
    city = forms.CharField(
        label=_("City"),
        max_length=64, required=False)
    postcode = forms.CharField(
        label=_("Post/Zip-code"),
        max_length=64, required=False)
    product_url = forms.URLField(
        max_length=192, label=_("amazon product url"),
        widget=forms.TextInput(attrs={
            'autocomplete': 'off',
            'class': 'form-control'
        }))
    mixpanel_anon_id = forms.CharField(
        widget=forms.HiddenInput, required=False)

    def __init__(self, *args, **kwargs):
        super(AmazonShippingCalculatorForm, self ).__init__(*args, **kwargs)
        self.set_country_queryset()

    def set_country_queryset(self):
        self.fields['country'].queryset = Country._default_manager.filter(
            is_shipping_country=True)

    def clean_product_url(self):
        data = self.cleaned_data.get('product_url')
        #make sure the link is taken from amazon US
        if not amazon_re.match(data.lower()):
            raise forms.ValidationError(_("Invalid Amazon US product url, only amazon.com supported"))
        return data
