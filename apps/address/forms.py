from django import forms
from oscar.apps.address.forms import UserAddressForm as CoreUserAddressForm
from .models import UserAddress
from django.db.models import get_model
from django.utils.translation import ugettext_lazy as _
from .validators import AddressValidators


Country = get_model('address', 'country')
US_STATES = (
    ('', '---------------'),
    ('AL', 'Alabama'),
    ('AK', 'Alaska'),
    ('AZ', 'Arizona'),
    ('AR', 'Arkansas'),
    ('CA', 'California'),
    ('CO', 'Colorado'),
    ('CT', 'Connecticut'),
    ('DE', 'Delaware'),
    ('DC', 'District of Columbia'),
    ('FL', 'Florida'),
    ('GA', 'Georgia'),
    ('HI', 'Hawaii'),
    ('ID', 'Idaho'),
    ('IL', 'Illinois'),
    ('IN', 'Indiana'),
    ('IA', 'Iowa'),
    ('KS', 'Kansas'),
    ('KY', 'Kentucky'),
    ('LA', 'Louisiana'),
    ('ME', 'Maine'),
    ('MD', 'Maryland'),
    ('MA', 'Massachusetts'),
    ('MI', 'Michigan'),
    ('MN', 'Minnesota'),
    ('MS', 'Mississippi'),
    ('MO', 'Missouri'),
    ('MT', 'Montana'),
    ('NE', 'Nebraska'),
    ('NV', 'Nevada'),
    ('NH', 'New Hampshire'),
    ('NJ', 'New Jersey'),
    ('NM', 'New Mexico'),
    ('NY', 'New York'),
    ('NC', 'North Carolina'),
    ('ND', 'North Dakota'),
    ('OH', 'Ohio'),
    ('OK', 'Oklahoma'),
    ('OR', 'Oregon'),
    ('PA', 'Pennsylvania'),
    ('RI', 'Rhode Island'),
    ('SC', 'South Carolina'),
    ('SD', 'South Dakota'),
    ('TN', 'Tennessee'),
    ('TX', 'Texas'),
    ('UT', 'Utah'),
    ('VT', 'Vermont'),
    ('VA', 'Virginia'),
    ('WA', 'Washington'),
    ('WV', 'West Virginia'),
    ('WI', 'Wisconsin'),
    ('WY', 'Wyoming'),
)

class UserAddressForm(CoreUserAddressForm, AddressValidators):
    def __init__(self, is_merchant=False, is_business_account=False, *args, **kwargs):
        super(UserAddressForm, self).__init__(*args, **kwargs)
        self.instance.is_merchant = is_merchant
        self.set_country_queryset(is_merchant, is_business_account)
        self.add_validators(self.fields)
        if is_merchant:
            if 'first_name' in self.fields:
                self.fields['first_name'].label = _("Merchant name")
                self.fields['first_name'].widget = forms.TextInput(attrs={'readonly': 'readonly'})
                #always take merchant name from db
                clean_func = "clean_first_name"
                old_method = getattr(self, clean_func, None)
                setattr(self, clean_func, self.lambder('first_name', old_method))
            if 'state' in self.fields:
                self.fields['state'].required = True
                self.fields['state'].widget = forms.Select(choices=US_STATES)
            del self.fields['last_name']
            if 'phone_number' in self.fields:
                self.fields['phone_number'].help_text = ''
                self.fields['phone_number'].label = 'Merchant phone number'
        else:
            #make phone number mandatory for personal address
            self.fields['phone_number'].required = True

    def lambder(self, field, old_method):
        return lambda: self.clean_field(field, old_method)

    def clean_field(self, field_name, old_method):
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            return getattr(instance, field_name) + ' RETURN ADDRESS'
        else:
            if old_method:
                return old_method(self)
            else:
                return self.cleaned_data.get(field_name, None)

    def set_country_queryset(self, is_merchant, is_business_account):
        if is_merchant:
            #return to merchant country is always US
            del self.fields['country']
            self.instance.country = Country.objects.get(iso_3166_1_a2='US')
        else:
            self.fields['country'].queryset = Country._default_manager.filter(
                is_shipping_country=True)
            if is_business_account:
                self.fields['country'].queryset |= Country._default_manager.filter(
                iso_3166_1_a2='US')

    class Meta:
        model = UserAddress
        exclude = ('user', 'num_orders', 'hash', 'search_text',
                   'is_default_for_billing', 'is_default_for_shipping',
                   'title', 'notes', 'is_merchant')
