from django.conf.urls import patterns, url
from oscar.core.application import Application
from django.contrib.auth.decorators import login_required
from . import views


class CatalogueApplication(Application):
    name = 'catalogue'
    detail_view = views.ProductDetailView
    #category_view = views.ProductCategoryView

    def get_urls(self):
        urlpatterns = super(CatalogueApplication, self).get_urls()
        urlpatterns += patterns('',
            url(r'^(?P<product_slug>[\w-]*)_(?P<pk>\d+)/$',
                login_required(self.detail_view.as_view()), name='detail'))
            #url(r'^(?P<category_slug>[\w-]+(/[\w-]+)*)/$',
            #    self.category_view.as_view(), name='category'))
        return self.post_process_urls(urlpatterns)

application = CatalogueApplication()
