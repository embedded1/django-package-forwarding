from django.conf.urls import patterns, url
from . import views
from django.contrib.auth.decorators import login_required
from oscar.core.application import Application


class ContactsApplication(Application):
    name = 'contacts'
    auth_view = views.AuthView
    invite_contacts_view = views.InviteContactsView
    invite_friends_view = views.InviteFriendsView

    def get_urls(self):
        urlpatterns = patterns('',
            url(r'^$', login_required(self.auth_view.as_view()), name='auth'),
            url(r'^invite/contacts/$', login_required(self.invite_contacts_view.as_view()), name='google-invite'),
            url(r'^invite/friends/$', login_required(self.invite_friends_view.as_view()), name='friends-invite'),
        )
        return self.post_process_urls(urlpatterns)


application = ContactsApplication()


