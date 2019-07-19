from oscar.apps.customer.forms import (
    EmailUserCreationForm as CoreEmailUserCreationForm,
    EmailAuthenticationForm as CoreEmailAuthenticationForm)
from oscar.apps.customer.forms import OrderSearchForm as CoreOrderSearchForm
from django.core.exceptions import ObjectDoesNotExist
from apps.user.models import Profile
from django.db.models import get_model
from apps.customer.models import CustomerFeedback
from oscar.apps.customer.forms import CommonPasswordValidator
from apps.catalogue.models import AdditionalPackageReceiver, PackageReceiverDocument
from apps.user.models import AccountStatus, AccountAuthenticationDocument
from django.forms.models import inlineformset_factory, BaseInlineFormSet
from django.utils.translation import ugettext_lazy as _
from django import forms
from apps.address.validators import alphanumeric_and_space_and_dash
from oscar.apps.customer.utils import normalise_email
from django.contrib.auth.models import User
from django.core import validators
from django.db.models import Q
from django.utils.crypto import get_random_string
import logging

Country = get_model('address', 'country')

logger = logging.getLogger("management_commands")

def generate_username():
    uname =  get_random_string(length=30)
    try:
        User.objects.get(username=uname)
        return generate_username()
    except User.DoesNotExist:
        return uname


class SettingsForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(SettingsForm, self).__init__(*args, **kwargs)
        self.fields['email'].required = True

    def clean_email(self):
        email = normalise_email(self.cleaned_data['email'])
        if User._default_manager.exclude(
                pk=self.instance.pk).filter(email=email).exists():
            raise forms.ValidationError(
                _("A user with that email address already exists."))
        return email

    class Meta:
        model = User
        fields = ('email', )


class ProfileForm(forms.ModelForm):
    def __init__(self, user=None, *args, **kwargs):
        self.user = user
        try:
            instance = Profile.objects.get(user=user)
        except ObjectDoesNotExist:
            if self.user:
                # User has no profile, try a blank one
                instance = Profile(user=user)
            else:
                instance = None
        if instance:
            kwargs['instance'] = instance
        super(ProfileForm, self).__init__(*args, **kwargs)
        self.fields['is_photos'].required = False


    class Meta:
        model = Profile
        widgets = {
          'is_custom_requests': forms.Textarea(attrs={'rows': 5, 'cols': 30}),
          #'is_photos': forms.RadioSelect(),
        }
        fields = (
            'is_consolidate_every_new_package', 'is_filling_customs_declaration',
            'is_repackaging', 'is_express_checkout', 'is_remove_invoice',
            'is_extra_protection', 'is_photos', 'is_custom_requests'
        )


class ProfileWithEmailForm(ProfileForm):
    email = forms.EmailField(
        label=_('Email address'))
    first_name = forms.CharField(
        label=_('First name'), max_length=30,
        validators=[alphanumeric_and_space_and_dash])
    last_name = forms.CharField(
        label=_('Last name'), max_length=30,
        validators=[alphanumeric_and_space_and_dash])
    country  = forms.ChoiceField(
        label=_("Where are you from?"))
    mixpanel_anon_id = forms.CharField(
        widget=forms.HiddenInput, required=False)

    def __init__(self, ip_country=None, bypass_email=False, *args, **kwargs):
        super(ProfileWithEmailForm, self).__init__(*args, **kwargs)
        self.set_country_queryset()
        self.ip_country = ip_country
        self.bypass_email = bypass_email

    def clean_email(self):
        email = normalise_email(self.cleaned_data['email'])

        if self.bypass_email:
            return email

        if User._default_manager.filter(email=email).exists():
            raise forms.ValidationError(
                _("A user with that email address already exists."))
        return email

    def set_country_queryset(self):
        #we allow customers from the US to open new account but they only be able to ship abroad
        countries = [(c.iso_3166_1_a3, c) for c in list(
            Country._default_manager\
                .filter(Q(is_shipping_country=True) | Q(iso_3166_1_a3='USA')))]
        self.fields['country'].choices = [('', '-------------')] + countries

    def clean(self):
        """
        Detect user country by IP address and make sure we can ship to this country
        """
        cleaned_data = super(ProfileWithEmailForm, self).clean()
        if not self._errors and self.ip_country:
            #exclude the US as we don't open it for shipping by default
            if self.ip_country != 'USA':
                try:
                    Country\
                    .objects\
                    .get(is_shipping_country=True,
                         iso_3166_1_a3=self.ip_country)
                except Country.DoesNotExist:
                    raise forms.ValidationError(_("Oh snap, we don't ship to your country."))
        return cleaned_data

    #def save(self, *args, **kwargs):
    #    profile = super(ProfileWithEmailForm, self).save(**kwargs)
    #    #mark that account setup has been completed
    #    profile.is_account_setup_completed = True
    #    return profile

    class Meta:
        model = Profile
        widgets = {
          'is_custom_requests': forms.Textarea(attrs={'rows': 3, 'cols': 30}),
          #'is_photos': forms.RadioSelect(),
        }
        fields = (
            'is_consolidate_every_new_package', 'is_filling_customs_declaration',
            'is_repackaging', 'is_express_checkout', 'is_remove_invoice',
            'is_extra_protection', 'is_photos', 'is_custom_requests', 'package_tracking'
        )


class ProfileWithEmailAndPasswordForm(ProfileWithEmailForm):
    password = forms.CharField(
        label=_('Password'), widget=forms.PasswordInput,
        validators=[validators.MinLengthValidator(6),
                    CommonPasswordValidator()])

    def clean_email(self):
        """
        Users can't change their email address here, so we cancel the validation
        This is a post-registration step where user already added into the db
        """
        return normalise_email(self.cleaned_data['email'])


class EmailAuthenticationForm(CoreEmailAuthenticationForm):
    def clean(self):
        """
        Check if te user didn't complete the registration process
        and show message if so
        """
        email = self.cleaned_data.get('username')
        try:
            user = User.objects.get(email=email)
            if not user.has_usable_password():
                raise forms.ValidationError(
                    _("You didn't complete the signup process."
                      " Check your email and follow the instructions before trying to log in"))
        except User.DoesNotExist:
            pass
        return super(EmailAuthenticationForm, self).clean()

class EmailUserCreationForm(CoreEmailUserCreationForm):
    def __init__(self, **kwargs):
        super(EmailUserCreationForm, self).__init__(**kwargs)
        self.fields.keyOrder = [
           'email', 'password1', 'redirect_url',
        ]


class OrderSearchForm(CoreOrderSearchForm):
    def __init__(self, *args, **kwargs):
        super(OrderSearchForm, self).__init__(*args, **kwargs)
        self.fields['date_from'] = forms.DateField(required=False, label=_("From"), input_formats=["%d.%m.%Y"])
        self.fields['date_to'] = forms.DateField(required=False, label=_("To"), input_formats=["%d.%m.%Y"])


class ShippingInsuranceClaimForm(forms.Form):
    MAX_FILE_SIZE = 5 * 1024 * 1024 #5MB
    owner = None
    invoice = forms.FileField(
        label=_("Merchant Invoice"),
        help_text=_("Select the invoice of the order you've delivered to us"))
    damaged_goods1 = forms.ImageField(
        label=_("Damaged Goods Snapshot"), required=False,
        help_text=_("Select a photo that shows a clear sign of the damage"))
    damaged_goods2 = forms.ImageField(
        label=_("Another Damaged Goods Snapshot"), required=False,
        help_text=_("Select another photo if one is not sufficient"))
    order_number = forms.CharField(
        label=_("USendHome Order Number"), max_length=128,
        help_text=_("Enter the order number we've emailed you"))
    incident_details = forms.CharField(
        label=_("Nature of The Claim"), max_length=1000,
        help_text=_("Describe in detail what went wrong with your order"),
        widget=forms.Textarea(attrs={'rows': 5, 'cols': 30}))


    def __init__(self, owner=None, *args, **kwargs):
        self.owner = owner
        super(ShippingInsuranceClaimForm, self).__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super(ShippingInsuranceClaimForm, self).clean()
        if not self._errors:
            invoice = cleaned_data.get('invoice')
            #check for file size
            if invoice and invoice.size > self.MAX_FILE_SIZE:
                raise forms.ValidationError(_("Invoice file is too large, ( > 5MB )"))
            damaged_goods1 = cleaned_data.get('damaged_goods1')
            #check for file size
            if damaged_goods1 and damaged_goods1.size > self.MAX_FILE_SIZE:
                raise forms.ValidationError(_("Damaged goods file is too large, ( > 5MB )"))
            damaged_goods2 = cleaned_data.get('damaged_goods2')
            #check for file size
            if damaged_goods2 and damaged_goods2.size > self.MAX_FILE_SIZE:
                raise forms.ValidationError(_("Damaged goods file is too large, ( > 5MB )"))
        return cleaned_data

    def clean_order_number(self):
        """
        Validate that order number belongs to customer
        and that the user has purchased shipping insurance
        and that the order shipped and that no shipping insurance claim was
        issued before
        """
        order_number = self.cleaned_data.get('order_number')
        try:
            order = self.owner.orders.get(number=order_number)
        except (AttributeError, ObjectDoesNotExist):
            raise forms.ValidationError(_("Order doesn't belong to you or doesn't exist"))
        if order.shipping_insurance_claim_issued:
            raise forms.ValidationError(_("You've already submitted an insurance claim for this order"))
        if order.status.lower() != 'shipped':
            raise forms.ValidationError(_("Order hasn't been shipped yet"))
        #if not order.shipping_insurance:
        #    raise forms.ValidationError(_("Shipping insurance wasn't purchased"))

        return order_number



class PackageTrackingForm(forms.ModelForm):
    def __init__(self, user, *args, **kwargs):
        self.user = user
        try:
            instance = Profile.objects.get(user=user)
        except ObjectDoesNotExist:
            if self.user:
                # User has no profile, try a blank one
                instance = Profile(user=user)
            else:
                instance = None
        if instance:
            kwargs['instance'] = instance
        super(PackageTrackingForm, self).__init__(*args, **kwargs)


    class Meta:
        model = Profile
        fields = ('package_tracking', )


class CustomerFeedbackForm(forms.ModelForm):
    def __init__(self, order, customer, *args, **kwargs):
        self.order = order
        self.customer = customer
        super(CustomerFeedbackForm, self).__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super(CustomerFeedbackForm, self).clean()
        if not any(self.errors):
            try:
                self.order.feedback
            except ObjectDoesNotExist:
                pass
            else:
                raise forms.ValidationError(_("We've already received your feedback for order %s,"
                                              " thanks again.") % self.order.number)
        return cleaned_data


    def save(self, commit=True):
        feedback = super(CustomerFeedbackForm, self).save(commit=False)
        feedback.order = self.order
        feedback.customer = self.customer
        feedback.save()
        return feedback

    class Meta:
        model = CustomerFeedback
        fields = ('question1', 'question2', 'question3', 'quote_testimonial')
        widgets = {
            'question1': forms.Textarea(attrs={'rows': 3, 'cols': 30}),
            'question2': forms.Textarea(attrs={'rows': 3, 'cols': 30}),
            'question3': forms.Textarea(attrs={'rows': 3, 'cols': 30}),
        }

class AdditionalPackageReceiverForm(forms.ModelForm):
    class Meta:
        model = AdditionalPackageReceiver
        exclude = ('package_owner', 'verification_status')

    def __init__(self, package_owner, *args, **kwargs):
        super(AdditionalPackageReceiverForm, self).__init__(*args, **kwargs)
        self.instance.package_owner = package_owner

    def clean(self):
        cleaned_data = super(AdditionalPackageReceiverForm, self).clean()
        if not any(self.errors):
            #make sure additional receiver wasn't already added
            try:
                AdditionalPackageReceiver.objects.get(
                    first_name__iexact=cleaned_data['first_name'],
                    last_name__iexact=cleaned_data['last_name'],
                    package_owner=self.instance.package_owner)
            except ObjectDoesNotExist:
                pass
            else:
                raise forms.ValidationError(_("%s %s is already exists.") % (
                    cleaned_data['first_name'], cleaned_data['last_name']))
            #make sure additional receiver is not the account owner
            try:
                User.objects.get(
                    id=self.instance.package_owner.id,
                    first_name__iexact=cleaned_data['first_name'],
                    last_name__iexact=cleaned_data['last_name'])
            except ObjectDoesNotExist:
                pass
            else:
                raise forms.ValidationError(_("Additional receiver name is identical to account holder name."))
        return cleaned_data


    def save(self, commit=True):
        obj = super(AdditionalPackageReceiverForm, self).save(commit=False)
        obj.verification_status = AdditionalPackageReceiver.VERIFICATION_IN_PROGRESS
        obj.save()
        return obj

class AdditionalPackageReceiverDocumentForm(forms.ModelForm):
    MAX_FILE_SIZE = 5 * 1024 *1024 #5MB

    def clean_original(self):
        document = self.cleaned_data.get('original')
        if document and document.size > self.MAX_FILE_SIZE:
            raise forms.ValidationError(_("Document file is too large, ( > 5MB )"))
        return document

    class Meta:
        model = PackageReceiverDocument
        fields = ('original', 'category')

class AccountAuthenticationDocumentForm(forms.ModelForm):
    MAX_FILE_SIZE = 5 * 1024 *1024 #5MB

    def clean_original(self):
        document = self.cleaned_data.get('original')
        if document and document.size > self.MAX_FILE_SIZE:
            raise forms.ValidationError(_("Document file is too large, ( > 5MB )"))
        return document

    class Meta:
        model = AccountAuthenticationDocument
        fields = ('original', 'category')

class BaseAuthenticationDocumentFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super(BaseAuthenticationDocumentFormSet, self).__init__(*args, **kwargs)
        for form in self.forms:
            form.empty_permitted = False

    def clean(self):
        cleaned_data = super(BaseAuthenticationDocumentFormSet, self).clean()
        if not any(self.errors):
            categories = []
            for form in self.forms:
                category = form.cleaned_data.get('category')
                if category in categories:
                    raise forms.ValidationError(_("Please select 2 different documents"))
                categories.append(category)
        return cleaned_data


class AffiliateCreationForm(EmailUserCreationForm):
    COUNTRY_CHOICES = [('', "Select Country")] + [(c.pk, c.printable_name) for c in Country.objects.all()]
    first_name = forms.CharField(
        label=_('First name'), max_length=30,
        validators=[alphanumeric_and_space_and_dash])
    last_name = forms.CharField(
        label=_('Last name'), max_length=30,
        validators=[alphanumeric_and_space_and_dash])
    line1 = forms.CharField(
        label=_("Address"), max_length=255)
    city = forms.CharField(
        label=_("City"), max_length=255)
    postcode = forms.CharField(
        label=_("Post/Zip-code"), max_length=64, required=False)
    country = forms.ChoiceField(
        label=_("Country"), choices=COUNTRY_CHOICES)
    website = forms.URLField(verify_exists=True)
    mixpanel_anon_id = forms.CharField(
        widget=forms.HiddenInput, required=False)

    def __init__(self, **kwargs):
        super(AffiliateCreationForm, self).__init__(**kwargs)
        self.fields.keyOrder = [
           'first_name', 'last_name', 'line1', 'city', 'postcode',
           'country', 'website', 'email', 'password1', 'mixpanel_anon_id',
        ]


AdditionalPackageReceiverDocumentFormSet = inlineformset_factory(
    AdditionalPackageReceiver, PackageReceiverDocument,
    form=AdditionalPackageReceiverDocumentForm,
    formset=BaseAuthenticationDocumentFormSet,
    fields=('category', 'original'), extra=2)

AccountAuthenticationDocumentFormSet = inlineformset_factory(
    AccountStatus, AccountAuthenticationDocument,
    form=AccountAuthenticationDocumentForm,
    formset=BaseAuthenticationDocumentFormSet,
    fields=('category', 'original'), extra=2)
