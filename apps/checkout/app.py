from oscar.apps.checkout.app import CheckoutApplication as CoreCheckoutApplication
from apps.checkout import views
from django.contrib.auth.decorators import login_required
from django.conf.urls import patterns, url


class CheckoutApplication(CoreCheckoutApplication):
    shipping_method_view = views.ShippingMethodView
    custom_view = views.CustomView
    shipping_address_view = views.ShippingAddressView
    return_to_store_shipping_address_view = views.ReturnToStoreShippingAddressView
    index_view = views.IndexView
    return_to_store_index_view = views.ReturnToStoreIndexView
    payment_method_view = views.PaymentMethodView
    payment_details_view = views.PaymentDetailsView
    thankyou_view = views.ThankYouView
    #basket_index_view = views.BasketIndexView
    add_voucher_view = views.VoucherAddView
    remove_voucher_view = views.VoucherRemoveView

    def get_urls(self):
        urlpatterns = super(CheckoutApplication, self).get_urls()

        new_urlpatterns = patterns('',
            url(r'^customs/$', login_required(self.custom_view.as_view()), name='customs'),
            url(r'^return-to-merchant/$', login_required(self.return_to_store_index_view.as_view()),
                name='return-to-store-index'),
            url(r'^return-to-merchant/shipping-address/$',
                login_required(self.return_to_store_shipping_address_view.as_view()),
                name='return-to-store-shipping-address'),
            #url(r'^basket/$', self.basket_index_view.as_view(permanent=False), name='basket'),
            url(r'^vouchers/add/$', login_required(self.add_voucher_view.as_view()),
                name='vouchers-add'),
            url(r'^vouchers/(?P<pk>\d+)/remove/$',
                login_required(self.remove_voucher_view.as_view()), name='vouchers-remove'),
        )

        return self.post_process_urls(new_urlpatterns) + urlpatterns


application = CheckoutApplication()

