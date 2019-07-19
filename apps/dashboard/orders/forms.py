from django import forms
from oscar.apps.dashboard.orders.forms import OrderSearchForm as CoreOrderSearchForm
from apps.order.models import ShippingLabelBatch
from django.utils.translation import ugettext_lazy as _


class ShippingLabelBatchForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(ShippingLabelBatchForm, self).__init__(*args, **kwargs)
        for key in self.fields:
            self.fields[key].required = False

    class Meta:
        model = ShippingLabelBatch
        exclude = (
            'orders', 'shipping_label',
            'date_created', 'date_updated'
        )

class PartialRefundForm(forms.Form):
    total_amount = forms.DecimalField(
        label=_("Total amount to refund"), decimal_places=2,
        max_digits=6)
    secondary_receiver_amount = forms.DecimalField(
        label=_("Amount to take from the secondary receiver, the rest will be taken"
          " from the primary receiver"), decimal_places=2,
        max_digits=6)

    def __init__(self, order, *args, **kwargs):
        self.order = order
        super(PartialRefundForm, self).__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super(PartialRefundForm, self).clean()
        if not self._errors:
            #partial refund can only be issued after partner received the payment
            if self.order.status != 'Processed':
                raise forms.ValidationError(_("Partial refund can't be issued before partner received the payment"))

            total_amount = cleaned_data.get('total_amount')
            if total_amount > self.order.total_incl_tax:
                raise forms.ValidationError(_("Total refund amount can not exceed order total(%s)"
                                            % self.order.total_incl_tax))
            partner_share = self.order.get_partner_payment_info()
            secondary_amount = cleaned_data.get('secondary_receiver_amount')
            if secondary_amount > partner_share:
                raise forms.ValidationError(_("Secondary refund amount can't exceed receiver's share(%s)"
                                              % partner_share))
        return cleaned_data


class OrderSearchForm(CoreOrderSearchForm):
    maxmind_trans_id = forms.CharField(
        required=False, label=_("Maxmind Tran ID"))

class BitcoinPaymentsForm(forms.Form):
    payments_file = forms.FileField(required=False)
    partner_paid = forms.BooleanField()
