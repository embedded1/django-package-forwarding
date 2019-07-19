from django.conf.urls import patterns, url
from . import views
from oscar.core.application import Application


class APIApplication(Application):
    name = 'api'
    forwarding_address_api_view = views.ForwardingAddressAPIView
    forwarding_address_create_view = views.ForwardingAddressCreateView
    chrome_amazon_shipping_methods_view = views.ChromeAmazonShippingMethodsView

    def get_urls(self):
        urlpatterns = patterns('',
            url(r'^address/forwarding.json/$',
                (self.forwarding_address_api_view.as_view()),
                name='forwarding-address'),
            url(r'^chrome/amazon/shipping-methods/$',
                self.chrome_amazon_shipping_methods_view.as_view(),
                name='chrome-amazon-shipping-methods'),
            url(r'^address/forwarding/create/$',
                (self.forwarding_address_create_view.as_view()),
                name='forwarding-address-create'),
        )
        return self.post_process_urls(urlpatterns)


application = APIApplication()


