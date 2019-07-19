from oscar.apps.dashboard.reports.app import ReportsApplication as CoreReportsApplication
from apps.dashboard.reports.views import IndexView


class ReportsApplication(CoreReportsApplication):
    index_view = IndexView
    permissions_map = {
        'reports-index': (['is_staff'], ['partner.dashboard_access'], ['partner.support_access']),
    }


application = ReportsApplication()
