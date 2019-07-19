from oscar.apps.dashboard.orders.app import OrdersDashboardApplication as CoreOrdersDashboardApplication
from apps.dashboard.orders import views
from django.conf.urls import patterns, url


class OrdersDashboardApplication(CoreOrdersDashboardApplication):
    default_permissions = ['is_staff', ]
    generate_shipping_labels_view = views.GenerateShippingLabelsView
    download_shipping_labels_view = views.PrintShippingLabelsView
    download_return_labels_view = views.DownloadReturnLabelsView
    batch_list_view = views.BatchListView
    batch_update_view = views.BatchUpdateView
    order_refund_view = views.OrderRefundView
    order_list_view = views.OrderListView
    process_bitcoin_payments_view = views.ProcessBitcoinPaymentsView
    incomplete_customs_declaration_view = views.IncompleteCustomsDeclarationNotificationView
    update_customs_declaration_view = views.UpdateCustomsDeclarationView
    add_itn_number_view = views.AddITNNumberView

    def __init__(self, app_name=None, **kwargs):
        super(OrdersDashboardApplication, self).__init__(app_name, **kwargs)
        self.permissions_map = {
            'order-detail': (['is_staff'], ['partner.support_access']),
            'generate-shipping-labels': (['is_staff'], ['partner.dashboard_access']),
            'print-shipping-labels': (['is_staff'], ['partner.dashboard_access']),
            'download-return-labels': (['is_staff'], ['partner.dashboard_access']),
            'incomplete-customs-declaration': (['is_staff'], ['partner.dashboard_access']),
            'update-customs-declaration': (['is_staff'], ['partner.dashboard_access']),
            'add-itn-number': (['is_staff'], ['partner.dashboard_access']),
            'batch-list': ['is_staff'],
            'batch-update': ['is_staff'],
            'bitcoin-processing': ['is_staff']
        }

    def get_urls(self):
        urlpatterns = super(OrdersDashboardApplication, self).get_urls()
        new_urlpatterns = patterns('',
            url(r'^shipping-labels/generate/$', self.generate_shipping_labels_view.as_view(),
                name='generate-shipping-labels'
            ),
            url(r'^shipping-labels/download/$', self.download_shipping_labels_view.as_view(),
                name='print-shipping-labels'
            ),
            url(r'^batches/$', self.batch_list_view.as_view(),
                name='batch-list'
            ),
            url(r'^batch/(?P<pk>\d+)/update/$', self.batch_update_view.as_view(),
                name='batch-update'
            ),
            url(r'^return-labels/download/$', self.download_return_labels_view.as_view(),
                name='download-return-labels'
            ),
            url(r'^refund/(?P<pk>\d+)/(?P<refund_type>\w+)/$', self.order_refund_view.as_view(),
                name='order-refund'
            ),
            url(r'^bitcoin/process/$', self.process_bitcoin_payments_view.as_view(),
                name='bitcoin-processing'
            ),
            url(r'^customs/incomplete/$', self.incomplete_customs_declaration_view.as_view(),
                name='incomplete-customs-declaration'
            ),
            url(r'^customs/update/(?P<pk>\d+)/$', self.update_customs_declaration_view.as_view(),
                name='update-customs-declaration'
            ),
            url(r'^itn/$', self.add_itn_number_view.as_view(),
                name='add-itn-number'
            ),
        )
        return self.post_process_urls(new_urlpatterns) + urlpatterns


application = OrdersDashboardApplication()
