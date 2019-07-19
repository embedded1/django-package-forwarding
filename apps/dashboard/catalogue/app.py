from oscar.apps.dashboard.catalogue.app import CatalogueApplication as CoreCatalogueApplication
from apps.dashboard.catalogue import views


class CatalogueApplication(CoreCatalogueApplication):
    permissions_map = _map = {
        'catalogue-product': (['is_staff'], ['partner.dashboard_access'], ['partner.support_access']),
        'catalogue-product-create': (['is_staff'], ['partner.dashboard_access']),
        'catalogue-product-list': (['is_staff'], ['partner.dashboard_access'], ['partner.support_access']),
        'catalogue-product-delete': (['is_staff'], ['partner.dashboard_access']),
        'catalogue-product-lookup': (['is_staff'], ['partner.dashboard_access']),
    }

    product_createupdate_view = views.CustomProductCreateUpdateView
    product_list_view = views.CustomProductListView
    product_delete_view = views.CustomProductDeleteView

application = CatalogueApplication()