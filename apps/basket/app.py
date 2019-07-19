from oscar.apps.basket.app import BasketApplication as CoreBasketApplication
from apps.basket.views import BasketView
from django.contrib.auth.decorators import login_required
from django.conf.urls import patterns, url

class BasketApplication(CoreBasketApplication):
    summary_view = BasketView

    def get_urls(self):
        """
        We override this function because we don't want to support basket views
        """
        urls = [url(r'^$', login_required(self.summary_view.as_view()), name='summary')]
        return self.post_process_urls(patterns('', *urls))

application = BasketApplication()
