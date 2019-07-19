from django.conf.urls.defaults import patterns, url
from django.contrib.admin.views.decorators import staff_member_required
from oscar.core.application import Application
from . import views


class BitcoinPayDashboardApplication(Application):
    name = None
    list_view = views.TransactionListView
    detail_view = views.TransactionDetailView
    ipn_list_view = views.PaymentsListView
    ipn_detail_view = views.PaymentDetailView

    def get_urls(self):
        urlpatterns = patterns('',
            url(r'^transactions/$', self.list_view.as_view(),
                name='bitcoinpay-transactions-list'),
            url(r'^transactions/(?P<pk>\d+)/$', self.detail_view.as_view(),
                name='bitcoinpay-transaction-detail'),
            url(r'^payments/$', self.ipn_list_view.as_view(),
                name='bitcoinpay-ipn-payment-list'),
            url(r'^payment/(?P<pk>\d+)/$', self.ipn_detail_view.as_view(),
                name='bitcoinpay-ipn-payment-detail'),
        )
        return self.post_process_urls(urlpatterns)

    def get_url_decorator(self, url_name):
        return staff_member_required


application = BitcoinPayDashboardApplication()
