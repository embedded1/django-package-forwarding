from oscar.apps.dashboard.users.app import UserManagementApplication as CoreUserManagementApplication
from apps.dashboard.users import views
from django.conf.urls import patterns, url


class UserManagementApplication(CoreUserManagementApplication):
    index_view = views.IndexView
    user_detail_view = views.UserDetailView
    user_lookup_view = views.UserLookupView
    user_feedback_list_view = views.UserFeedbackListView
    user_feedback_view = views.UserFeedbackView
    user_profile_update_view = views.UserProfileUpdateView
    user_geo_breakdown_view = views.UserGeoBreakdown
    user_registration_type_breakdown_view = views.UserRegistrationTypeBreakdown

    def __init__(self, app_name=None, **kwargs):
        super(UserManagementApplication, self).__init__(app_name, **kwargs)
        self.permissions_map.update({
            'users-index': (['is_staff'], ['partner.support_access']),
            'user-detail': (['is_staff'], ['partner.support_access']),
            'user-lookup': (['is_staff'], ['partner.dashboard_access']),
        })

    def get_urls(self):
        urls = super(UserManagementApplication, self).get_urls()
        new_urls = [
            url(r'^user-lookup/$', self.user_lookup_view.as_view(),
                name='user-lookup'),
            url(r'^feedback/$', self.user_feedback_list_view.as_view(),
                name='user-feedback-list'),
            url(r'^feedback/(?P<pk>\d+)/$',
                self.user_feedback_view.as_view(),
                name='user-feedback'),
            url(r'^profile/update/(?P<pk>\d+)/$',
                self.user_profile_update_view.as_view(),
                name='user-profile-update'),
            url(r'^geo/$',
                self.user_geo_breakdown_view.as_view(),
                name='user-geo-breakdown'),
            url(r'^registration-type/$',
                self.user_registration_type_breakdown_view.as_view(),
                name='user-registration-type-breakdown'),
        ]
        return urls + self.post_process_urls(patterns('', *new_urls))

application = UserManagementApplication()
