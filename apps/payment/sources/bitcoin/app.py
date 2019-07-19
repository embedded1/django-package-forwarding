from django.conf.urls import patterns, url
from apps.payment.sources.bitcoin import views
from oscar.core.application import Application

class BitcoinApplication(Application):
    name = None

    def get_urls(self):
        urls = [
            url(r'^preview/$',
                views.SuccessResponseView.as_view(),
                name='bitcoin-success-response'),
            url(r'^redirect/', views.RedirectView.as_view(),
                name='bitcoin-redirect'),
            url(r'^cancel/$', views.CancelResponseView.as_view(),
                name='bitcoin-cancel-response'),
        ]
        return self.post_process_urls(patterns('', *urls))

application = BitcoinApplication()

