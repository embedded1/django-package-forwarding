from django.conf.urls import patterns, include, url
#from paypal.express.views import RedirectView
#from apps.paypal_express.views import SuccessResponseView
from paypal.adaptive.views import (
    RedirectView, SuccessResponseView,
    CancelResponseView)
from packageshop.app import application as shop
from django.contrib import admin
from django.conf import settings
from oscar.views import handler500, handler404, handler403
import analytics


if settings.DEBUG:
    def on_error(error, items):
        print("An error occurred:", error)
    analytics.debug = True
    analytics.on_error = on_error
analytics.write_key = '7cXnTOvheZH371DARxUrUOHl2Tag0GHX'
admin.autodiscover()

urlpatterns = patterns('',
    #url(r'^checkout/paypal/place-order/(?P<basket_id>\d+)/$', SuccessResponseView.as_view(),
    #    name='paypal-place-order'),
    #url(r'^checkout/paypal/preview/(?P<basket_id>\d+)/$',
    #    SuccessResponseView.as_view(preview=True),
    #    name='paypal-success-response'),
    #url(r'^checkout/paypal/redirect/', RedirectView.as_view(as_payment_method=True),
    #    name='paypal-redirect'),
    url(r'^checkout/paypal/place-order/(?P<basket_id>\d+)/$', SuccessResponseView.as_view(),
        name='paypal-place-order'),
    url(r'^checkout/paypal/preview/(?P<basket_id>\d+)/$',
        SuccessResponseView.as_view(),
        name='paypal-success-response'),
    url(r'^checkout/paypal/redirect/', RedirectView.as_view(as_payment_method=True),
        name='paypal-redirect'),
    url(r'^checkout/paypal/cancel/(?P<basket_id>\d+)/$', CancelResponseView.as_view(),
        name='paypal-cancel-response'),
    url(r"^referrals/", include("pinax.referrals.urls")),
    url(r"^affiliates/", include("pinax.referrals.urls")),
    url(r'^sitemap.xml', include('static_sitemaps.urls')),
    (r'^admin/', include(admin.site.urls)),
    (r'', include(shop.urls)),
)

if settings.DEBUG:
    urlpatterns += patterns('',
        url(r'^static/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': settings.STATIC_ROOT, 'show_indexes': True}),
        url(r'^media/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': settings.MEDIA_ROOT, 'show_indexes': True})
        )

    # Allow error pages to be tested
    urlpatterns += patterns('',
        url(r'^403$', handler403),
        url(r'^404$', handler404),
        url(r'^500$', handler500),
    )
