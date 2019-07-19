from oscar.apps.dashboard.partners.app import PartnersDashboardApplication as CorePartnersDashboardApplication
from apps.dashboard.partners import views


class PartnersDashboardApplication(CorePartnersDashboardApplication):
    manage_view = views.PartnerManageView


application = PartnersDashboardApplication()