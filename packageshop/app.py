from oscar.app import Shop
from django.conf.urls import patterns, url, include
from django.contrib import admin
from django.views.generic import RedirectView
from django.core.urlresolvers import reverse_lazy
#from paypal.express.dashboard.app import application as express_dashboard
from paypal.adaptive.dashboard.app import application as adaptive_dashboard
from paypal.ipn.dashboard.app import application as ipn_dashboard
from apps.catalogue.app import application as catalogue_app
from apps.dashboard.app import application as dashboard_app
from apps.customer.app import application as customer_app
from apps.checkout.app import application as checkout_app
from apps.shipping_calculator.app import application as shipping_calculator_app
from apps.custom_social_auth.app import application as custom_social_auth_app
from apps.basket.app import application as basket_app
from apps.webhooks.app import application as webhooks_app
from apps.static.app import application as static_app
from apps.promotions.app import application as promotions_app
from apps.offer.app import application as offer_app
from apps.search.app import application as search_app
from apps.contacts.app import application as contacts_app
from apps.payment.sources.bitcoin.app import application as bitcoin_app
from apps.payment.sources.bitcoin.dashboard.app import application as bitcoin_dashboard_app
from apps.payment.sources.bitcoinpay.app import application as bitcoinpay_app
from apps.payment.sources.bitcoinpay.dashboard.app import application as bitcoinpay_dashboard_app
from apps.api.app import application as api_app

admin.autodiscover()


class BaseApplication(Shop):
    catalogue_app = catalogue_app
    dashboard_app = dashboard_app
    customer_app = customer_app
    checkout_app = checkout_app
    basket_app = basket_app
    shipping_calculator_app = shipping_calculator_app
    custom_social_auth_app = custom_social_auth_app
    webhooks_app = webhooks_app
    static_app = static_app
    promotions_app = promotions_app
    offer_app = offer_app
    search_app = search_app
    contacts_app = contacts_app
    # BitsOfGold
    bitcoin_app = bitcoin_app
    bitcoin_dashboard_app = bitcoin_dashboard_app
    # BitcoinPay
    bitcoinpay_app = bitcoinpay_app
    bitcoinpay_dashboard_app = bitcoinpay_dashboard_app
    api_app = api_app

    def get_urls(self):
        urlpatterns = super(BaseApplication, self).get_urls()

        new_urlpatterns = patterns('',
            #(r'^checkout/paypal/', include('paypal.express.urls')),
            #(r'^dashboard/paypal/express/', include(express_dashboard.urls)),
            (r'^checkout/paypal/', include('paypal.adaptive.urls')),
            (r'^dashboard/paypal/adaptive/', include(adaptive_dashboard.urls)),
            (r'^dashboard/paypal/ipn/', include(ipn_dashboard.urls)),
            (r'^checkout/bitcoin/', include(bitcoin_app.urls)),
            (r'^dashboard/bitcoin/transactions/', include(bitcoin_dashboard_app.urls)),
            (r'^dashboard/bitcoin/ipn/', include(bitcoin_dashboard_app.urls)),
            (r'^checkout/bitcoinpay/', include(bitcoinpay_app.urls)),
            (r'^dashboard/bitcoinpay/transactions/', include(bitcoinpay_dashboard_app.urls)),
            (r'^dashboard/bitcoinpay/ipn/', include(bitcoinpay_dashboard_app.urls)),
            (r'^custom_social_auth/', include(self.custom_social_auth_app.urls)),
            (r'^webhooks/', include(self.webhooks_app.urls)),
            (r'^contacts/', include(self.contacts_app.urls)),
            (r'^api/', include(self.api_app.urls)),
            (r'', include(self.shipping_calculator_app.urls)),
            (r'', include(self.static_app.urls)),
            (r'', include('social.apps.django_app.urls', namespace='social')),
            (r'hunger', include('hunger.urls')),
            url(r'^calculators/package/$',
                RedirectView.as_view(url=reverse_lazy('calculators:package'))),
            url(r'^calculators/amazon/$',
                RedirectView.as_view(url=reverse_lazy('calculators:amazon'))),
            url(r'^fees/$',
                RedirectView.as_view(url=reverse_lazy('fees-explained'))),
        )

        return new_urlpatterns + urlpatterns


application = BaseApplication()