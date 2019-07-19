from django.conf.urls import patterns, url
from oscar.apps.promotions.app import PromotionsApplication as CorePromotionsApplication
from .views import HomeView


class PromotionsApplication(CorePromotionsApplication):
    name = 'promotions'

    home_view = HomeView

    def get_urls(self):
        urls = [
            url(r'^$', self.home_view.as_view(), name='home'),
        ]
        return self.post_process_urls(patterns('', *urls))


application = PromotionsApplication()

