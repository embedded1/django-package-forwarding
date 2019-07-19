from django.conf.urls import patterns, url
from apps.dashboard.tools import views
from oscar.core.application import Application



class ToolsDashboardApplication(Application):
    name = None

    update_pending_fraud_check_order_view = views.UpdatePendingFraudCheckOrder
    resume_user_account_view = views.ResumeUserAccountView
    update_account_status_view = views.UpdateAccountStatus
    update_additional_package_receiver_view = views.UpdateAdditionalPackageReceiver

    default_permissions = ['is_staff', ]

    def get_urls(self):
        urlpatterns = patterns('',
            url(r'^update_pending_fraud_check_order/(?P<order_num>\d+)/$',
                self.update_pending_fraud_check_order_view.as_view(), name='pending-fraud-order'),
            url(r'^resume_user_account/(?P<user_num>\d+)/$',
                self.resume_user_account_view.as_view(), name='resume-user-account'),
            url(r'^account-status/update/(?P<pk>\d+)/$',
                self.update_account_status_view.as_view(), name='update-account-status'),
            url(r'^additional-receiver/update/(?P<pk>\d+)/$',
                self.update_additional_package_receiver_view.as_view(), name='update-additional-receiver'),
        )
        return self.post_process_urls(urlpatterns)


application = ToolsDashboardApplication()
