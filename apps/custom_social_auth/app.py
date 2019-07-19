from django.conf.urls import patterns, url
from apps.custom_social_auth import views
from oscar.core.application import Application


class CustomSocialAuthApplication(Application):
    name = 'custom_social_auth'
    custom_social_auth_profile_view = views.CustomSocialAuthProfileView
    custom_social_auth_error_view = views.CustomSocialAuthErrorView

    def get_urls(self):
        urlpatterns = patterns('',
            url(r'^register/services/$', self.custom_social_auth_profile_view.as_view(), name='profile-form'),
            url(r'^login-error/$', self.custom_social_auth_error_view.as_view(), name='social-login-error'),
        )
        return self.post_process_urls(urlpatterns)


application = CustomSocialAuthApplication()

