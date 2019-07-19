from django import forms
from oscar.apps.dashboard.partners.forms import PartnerAddressForm as CorePartnerAddressForm
from apps.partner.models import (
    PartnerAddress,
    PartnerOrderPaymentSettings)
from django.conf import settings


class PartnerAddressForm(CorePartnerAddressForm):
    class Meta:
        model = PartnerAddress
        fields = ('line1', 'line2', 'line3', 'line4',
                  'state', 'postcode', 'country', 'phone_number')


class PartnerOrderPaymentSettingsForm(forms.ModelForm):
    CARRIERS_CHOICES = (
        (settings.EASYPOST_USPS, 'USPS'),
        (settings.EASYPOST_FEDEX, 'FedEx'),
        (settings.EASYPOST_UPS, 'UPS'),
        (settings.EASYPOST_TNTEXPRESS, 'TNT'),
        (settings.EASYPOST_ARAMEX, 'Aramex'),
        (settings.EASYPOST_DHL, 'DHL'),
    )

    def __init__(self, *args, **kwargs):
        super(PartnerOrderPaymentSettingsForm, self).__init__(*args, **kwargs)
        self.fields['paid_carriers'] = forms.MultipleChoiceField(choices=self.CARRIERS_CHOICES)
        if 'instance' in kwargs:
            self.initial['paid_carriers'] = kwargs['instance'].paid_carriers.split(',')

    def clean_paid_carriers(self):
        paid_carriers = self.cleaned_data.get('paid_carriers')
        return ",".join(paid_carriers)

    class Meta:
        model = PartnerOrderPaymentSettings
        fields = (
            'billing_email', 'payment_gateway',
            'shipping_margin', 'services_margin',
            'paid_carriers', 'is_paying_shipping_insurance',
            'is_active', 'are_shipping_offers_apply'
        )