from oscar.apps.customer.app import CustomerApplication as CoreCustomerApplication
from . import views
from .notifications import views as notification_views
from django.contrib.auth.decorators import login_required
from django.conf.urls import patterns, url

class CustomerApplication(CoreCustomerApplication):
    settings_view = views.SettingsView
    settings_update_view = views.SettingsUpdateView
    profile_view = views.ProfileView
    profile_update_view = settings_update_view
    email_list_view = views.EmailHistoryView
    login_view = views.AccountAuthView
    register_view = views.AccountRegistrationView
    pending_packages_view = views.PendingPackagesView
    waiting_for_consolidation_packages_view = views.WaitingForConsolidationPackagesView
    register_profile_view = views.RegisterProfileView
    api_complete_registration_view = views.APICompleteRegistrationView
    notification_detail_view = notification_views.DetailView
    notification_inbox_view = notification_views.InboxView
    #close_account_view = views.CloseAccountView
    shipping_insurance_claim_view = views.ShippingInsuranceClaimView
    address_create_view = views.AddressCreateView
    address_update_view = views.AddressUpdateView
    address_change_status_view = views.AddressChangeStatusView
    address_list_view = views.AddressListView
    address_delete_view = views.AddressDeleteView
    email_confirmation_send_view = views.SendEmailConfirmationView
    email_confirmation_confirm_view = views.ConfirmEmailConfirmationView
    order_history_view = views.OrderHistoryView
    order_detail_view = views.OrderDetailView
    order_invoice_view = views.OrderInvoiceView
    extra_services_handling_view = views.ExtraServicesHandlingView
    change_password_view = views.ChangePasswordView
    package_tracking_view = views.PackageTrackingView
    tour_started_view = views.TourStartedView
    feedback_view = views.FeedbackView
    additional_receiver_create_view = views.AdditionalReceiverCreateView
    additional_receiver_list_view = views.AdditionalReceiverListView
    additional_receiver_delete_view = views.AdditionalReceiverDeleteView
    additional_receiver_verify_view = views.AdditionalReceiverVerifyView
    account_verify_view = views.AccountVerifyView
    referral_index_view = views.ReferralIndexView
    logout_view = views.LogoutView
    account_setup_view = views.AccountSetupView
    affiliate_register_view = views.AffiliateRegisterView


    def get_urls(self):
        urlpatterns = super(CustomerApplication, self).get_urls()
        urls = [
            url(r'^settings/$',
                login_required(self.settings_view.as_view()),
                name='settings-view'),
            url(r'^settings/edit/$',
                login_required(self.settings_update_view.as_view()),
                name='settings-update'),
            url(r'^profile/(?P<uidb36>[0-9A-Za-z]{1,13})-(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})-'
                r'(?P<club>[0-9A-Za-z+/=]{1,})/$',
                login_required(self.profile_view.as_view()),
                name='exclusive-club-join'),
            url(r'^register/services/$',
                self.register_profile_view.as_view(),
                name='register-settings'),
            url(r'^register/services/(?P<uidb36>[0-9A-Za-z]{1,13})-(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})-'
                r'(?P<issuer>[0-9A-Za-z+/=]{1,})/$',
                self.api_complete_registration_view.as_view(),
                name='api-complete-registration'),
            url(r'^package/incoming/$',
                login_required(self.pending_packages_view.as_view()),
                name='pending-packages'),
            url(r'^package/consolidation/$',
                login_required(self.waiting_for_consolidation_packages_view.as_view()),
                name='waiting-for-consolidation-packages'),
            url(r'^package/tracking/$',
                login_required(self.package_tracking_view.as_view()),
                name='package-tracking'),
            #url(r'^account/close/$',
            #    login_required(self.close_account_view.as_view()),
            #    name='close-account'),
            url(r'^insurance/claim/$',
                login_required(self.shipping_insurance_claim_view.as_view()),
                name='insurance-claim'),
            url(r'^email/confirmation/$',
                login_required(self.email_confirmation_send_view.as_view()),
                name='email-confirmation-send'),
            url(r'^email/confirmation/(?P<uidb36>[0-9A-Za-z]{1,13})-(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$',
                self.email_confirmation_confirm_view.as_view(),
                name='email-confirmation-confirm'),
            url(r'^extra-services/handling/(?P<package_pk>\d+)/$',
                login_required(self.extra_services_handling_view.as_view()),
                name='extra-services-handling'),
            url(r'^orders/(?P<order_number>[\w-]*)/invoice/$',
                login_required(self.order_invoice_view.as_view()),
                name='order-invoice'),
            url(r'^welcome-tour/$',
                login_required(self.tour_started_view.as_view()),
                name='tour-started'),
            url(r'^feedback/(?P<pk>\d+)/$',
                login_required((self.feedback_view.as_view())),
                name='feedback'),
            url(r'^additional-receiver/$',
                login_required((self.additional_receiver_list_view.as_view())),
                name='additional-receiver-list'),
            url(r'^additional-receiver/add/$',
                login_required((self.additional_receiver_create_view.as_view())),
                name='additional-receiver-create'),
            url(r'^additional-receiver/(?P<pk>\d+)/delete/$',
                login_required((self.additional_receiver_delete_view.as_view())),
                name='additional-receiver-delete'),
            url(r'^additional-receiver/(?P<pk>\d+)/verify/$',
                login_required((self.additional_receiver_verify_view.as_view())),
                name='additional-receiver-verify'),
            url(r'^(?P<pk>\d+)/verify/$',
                login_required((self.account_verify_view.as_view())),
                name='account-verify'),
            url(r'^referrals/$',
                login_required(self.referral_index_view.as_view()),
                name='referrals-index'),
            url(r'^affiliates/$',
                login_required(self.referral_index_view.as_view()),
                name='affiliates-index'),
            url(r'^setup/$',
                login_required(self.account_setup_view.as_view()),
                name='account-setup'),
            url(r'^affiliate/register/$',
                self.affiliate_register_view.as_view(),
                name='affiliate-register'),
        ]

        return self.post_process_urls(patterns('', *urls)) + urlpatterns

application = CustomerApplication()
