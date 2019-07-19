from django.conf.urls import patterns, url
from . import views
from oscar.core.application import Application
from django.views.generic import RedirectView

class WebHookApplication(Application):
    name = 'webhooks'
    easypost_tracker_view = views.EasyPostTrackerWebHookView
    paypal_ipn_view = views.PayPalIPNView
    bitcoin_ipn_view = views.BitcoinIPNView
    bitcoinpay_ipn_view = views.BitcoinpayIPNView

    def get_urls(self):
        urlpatterns = patterns('',
            url(r'^easypost/tracker/$',
                self.easypost_tracker_view.as_view(),
                name='easypost-tracker'),
            url(r'^paypal/ipn/$',
                self.paypal_ipn_view.as_view(),
                name='paypal-ipn'),
            url(r'^bitcoin/ipn/$',
                self.bitcoin_ipn_view.as_view(),
                name='bitcoin-ipn'),
            url(r'^bitcoinpay/ipn/$',
                self.bitcoinpay_ipn_view.as_view(),
                name='bitcoinpay-ipn'),
            url(r'^chrome/amazon/shipping-methods/$',
                RedirectView.as_view(url='/api/chrome/amazon/shipping-methods/')),
            #url(r'^paypal/ipn/(?P<basket_id>\d+)/$', self.paypal_ipn_view.as_view(), name='paypal-ipn')
        )
        return self.post_process_urls(urlpatterns)

application = WebHookApplication()
