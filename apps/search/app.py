from oscar.apps.search.app import SearchApplication as CoreSearchApplication
from django.conf.urls import patterns, url
from django.views.defaults import page_not_found

class SearchApplication(CoreSearchApplication):
    def get_urls(self):
        """
        We override this function because we don't want to support basket views
        """
        urlpatterns = patterns(
            '',
            url(r'^$', page_not_found, name='search'),
        )
        return self.post_process_urls(urlpatterns)

application = SearchApplication()

