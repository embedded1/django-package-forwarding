from django.conf.urls import patterns, url
from apps.payment.sources.bitcoinpay import views
from oscar.core.application import Application

class BitcoinPayApplication(Application):
    name = None

    def get_urls(self):
        urls = [
            url(r'^preview/(?P<basket_id>\d+)/$',
                views.SuccessResponseView.as_view(),
                name='bitcoinpay-success-response'),
            url(r'^redirect/', views.RedirectView.as_view(),
                name='bitcoinpay-redirect'),
        ]
        return self.post_process_urls(patterns('', *urls))

application = BitcoinPayApplication()

