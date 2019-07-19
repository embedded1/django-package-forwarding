from oscar.apps.offer.app import OfferApplication as CoreOfferApplication
from django.conf.urls import patterns, url
from django.views.defaults import page_not_found
from .views import OfferDetailView


class OfferApplication(CoreOfferApplication):
    detail_view = OfferDetailView

    def get_urls(self):
        """
        We override this function because we don't want to support basket views
        """
        urls = [
            url(r'^$', page_not_found, name='list'),
            url(r'^(?P<slug>[\w-]+)/$', self.detail_view.as_view(), name='detail'),
        ]
        return self.post_process_urls(patterns('', *urls))

application = OfferApplication()

