from django.conf.urls import patterns, url
from apps.shipping_calculator import views
from oscar.core.application import Application


class ShippingCalculatorApplication(Application):
    name = 'calculators'
    calculator_view = views.ShippingCalculatorView
    amazon_calculator_view = views.AmazonShippingCalculatorView

    def get_urls(self):
        urlpatterns = patterns('',
            url(r'^package-shipping-calculator/$', self.calculator_view.as_view(), name='package'),
            url(r'^amazon-shipping-calculator/$', self.amazon_calculator_view.as_view(), name='amazon'),
        )
        return self.post_process_urls(urlpatterns)


application = ShippingCalculatorApplication()
