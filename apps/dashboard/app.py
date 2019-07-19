from oscar.apps.dashboard.app import DashboardApplication as CoreDashboardApplication
from django.conf.urls import patterns, url, include
from apps.dashboard.views import IndexView
from apps.dashboard.catalogue.app import application as catalogue_app
from apps.dashboard.tools.app import application as tools_app
from apps.dashboard.reports.app import application as reports_app
from apps.dashboard.orders.app import application as orders_app
from apps.dashboard.users.app import application as users_app
from apps.dashboard.partners.app import application as partners_app


class DashboardApplication(CoreDashboardApplication):
    permissions_map = {
        'index': (['is_staff'], ['partner.dashboard_access'], ['partner.support_access']),
    }
    index_view = IndexView
    catalogue_app = catalogue_app
    tools_app = tools_app
    reports_app = reports_app
    orders_app = orders_app
    users_app = users_app
    partners_app = partners_app

    def get_urls(self):
        urlpatterns = super(DashboardApplication, self).get_urls()

        new_urlpatterns = patterns('',
            url(r'^$', self.index_view.as_view(), name='index'),
            url(r'^tools/', include(self.tools_app.urls)),
        )

        return self.post_process_urls(new_urlpatterns) + urlpatterns

application = DashboardApplication()