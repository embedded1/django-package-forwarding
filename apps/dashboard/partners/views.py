from oscar.apps.dashboard.partners.views import PartnerManageView as CorePartnerManageView
from oscar.core.loading import get_classes
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext as _
from apps.partner.models import Partner


PartnerOrderPaymentSettingsForm, PartnerAddressForm = get_classes(
    'dashboard.partners.forms',
    ['PartnerOrderPaymentSettingsForm',
     'PartnerAddressForm'])


class PartnerManageView(CorePartnerManageView):
    order_payment_settings_form_class = PartnerOrderPaymentSettingsForm
    address_form_class = PartnerAddressForm

    def dispatch(self, request, *args, **kwargs):
        self.partner = self.object = get_object_or_404(
            Partner, pk=kwargs['pk'])
        self.address = self.partner.primary_address
        if self.address is None:
            self.address = self.partner.addresses.model(partner=self.partner)
        self.order_payment_settings = self.partner.active_payment_settings
        if not self.order_payment_settings:
            self.order_payment_settings = self.partner.payments_settings.model(partner=self.partner)
        return super(PartnerManageView, self).dispatch(
            request, *args, **kwargs)


    def get_context_data(self, partner_form, address_form, **kwargs):
        ctx = super(PartnerManageView, self).get_context_data(partner_form, address_form, **kwargs)
        if 'order_payment_settings_form' not in kwargs:
            ctx['order_payment_settings_form'] = self.order_payment_settings_form_class(
                instance=self.order_payment_settings)
        else:
            ctx['order_payment_settings_form'] = kwargs['order_payment_settings_form']
        return ctx

    def post(self, request, *args, **kwargs):
        if request.POST['submit'] == 'partner_order_payment_settings_form':
            order_payment_settings_form = self.order_payment_settings_form_class(
                request.POST, instance=self.order_payment_settings)
            if order_payment_settings_form.is_valid():
                order_payment_settings_form.save()
                messages.success(
                    self.request, _("Order payment settings was updated successfully."))
            partner_form = self.partner_form_class(instance=self.partner)
            address_form = self.address_form_class(instance=self.address)
        elif request.POST['submit'] == 'partner_form':
            partner_form = self.partner_form_class(
                request.POST, instance=self.partner)
            if partner_form.is_valid():
                self.partner = self.object = partner_form.save()
                messages.success(
                    self.request, _("Partner '%s' was updated successfully.") %
                    self.object.name)
            address_form = self.address_form_class(instance=self.address)
            order_payment_settings_form = self.order_payment_settings_form_class(instance=self.order_payment_settings)
        else:
            address_form = self.address_form_class(
                request.POST, instance=self.address)
            if address_form.is_valid():
                address_form.save()
                messages.success(
                    self.request, _("Address was updated successfully."))
            partner_form = self.partner_form_class(instance=self.partner)
            order_payment_settings_form = self.order_payment_settings_form_class(instance=self.order_payment_settings)

        context = self.get_context_data(
            partner_form, address_form,
            order_payment_settings_form=order_payment_settings_form)

        return self.render_to_response(context)