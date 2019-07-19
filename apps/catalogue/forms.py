from django import forms
from apps.catalogue.models import ProductSpecialRequests
from django.conf import settings


class SpecialRequestsForm(forms.ModelForm):
    package = None

    def __init__(self, package, *args, **kwargs):
        super(SpecialRequestsForm, self).__init__(*args, **kwargs)
        #for consolidated packages we exclude the repackaging and taking photos options
        #for waiting for consolidation packages we exclude all special requests except for taking photos
        self.package = package
        if self.package.is_consolidated:
            excluded_special_requests = settings.CONSOLIDATED_EXCLUDED_SPECIAL_REQUESTS
        elif self.package.is_waiting_for_consolidation:
            excluded_special_requests = settings.WAITING_FOR_CONSOLIDATION_EXCLUDED_SPECIAL_REQUESTS
        else:
            excluded_special_requests = []

        if excluded_special_requests:
            for key in self.fields.keys():
                if key in excluded_special_requests:
                    self.fields.pop(key)
        #we need to disable input fields that the user has chosen, there is no turning back
        #user can't cancel special requests that was already completed
        instance = kwargs.get('instance')
        if instance:
            self.requested_special_requests_attr_names = instance.requested_special_requests_attr_names()
        else:
            self.requested_special_requests_attr_names = []
        for field_name in self.requested_special_requests_attr_names:
            try:
                self.fields[field_name].widget.attrs['onclick'] = 'return false;'
                self.fields[field_name].widget.attrs['readonly'] = ''
                clean_func = "clean_" + field_name
                old_method = getattr(self, clean_func, None)
                setattr(self, clean_func, self.lambder(field_name, old_method))
            except KeyError:
                continue
        try:
            self.fields['is_photos'].required = False
        except KeyError:
            pass

    def lambder(self, field, old_method):
        return lambda: self.clean_field(field, old_method)

    def clean_field(self, field_name, old_method):
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            return getattr(instance, field_name)
        else:
            if old_method:
                return old_method(self)
            else:
                return self.cleaned_data.get(field_name, None)

    def save(self, commit=True):
        self.instance.package = self.package
        return super(SpecialRequestsForm, self).save(commit)

    class Meta:
        model = ProductSpecialRequests
        widgets = {
            'is_custom_requests': forms.Textarea(attrs={'rows': 3, 'cols': 30}),
        }
        exclude = ('filling_customs_declaration_done', 'repackaging_done',
                   'express_checkout_done', 'photos_done', 'custom_requests_done',
                   'custom_requests_details', 'remove_invoice_done',
                   'extra_protection_done', 'package')





