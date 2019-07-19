from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_class
from django.contrib.auth.models import User
from django.db.models import Count
from apps.user.models import AccountStatus
from decimal import Decimal as D
from django.db.models import Q
from operator import itemgetter

ReportGenerator = get_class('dashboard.reports.reports', 'ReportGenerator')
ReportCSVFormatter = get_class('dashboard.reports.reports', 'ReportCSVFormatter')
ReportHTMLFormatter = get_class('dashboard.reports.reports', 'ReportHTMLFormatter')


class SuspendedUserAccountReportHTMLFormatter(ReportHTMLFormatter):
    filename_template = 'dashboard/reports/partials/suspended_users_report.html'


class SuspendedUserAccountReportGenerator(ReportGenerator):
    code = 'suspended_users_report'
    description = _("Suspended accounts")

    formatters = {
        'CSV_formatter': None,
        'HTML_formatter': SuspendedUserAccountReportHTMLFormatter,
    }

    def generate(self):
        suspended_users = User.objects.filter(is_active=False)

        additional_data = {
            'start_date': self.start_date,
            'end_date': self.end_date
        }

        return self.formatter.generate_response(suspended_users, **additional_data)

    def is_available_to(self, user):
        return user.is_staff

class AccountStatusActionReportHTMLFormatter(ReportHTMLFormatter):
    filename_template = 'dashboard/reports/partials/account_status_report.html'


class AccountStatusActionReportGenerator(ReportGenerator):
    code = 'accounts_status_verification_report'
    description = _("Accounts waiting for verification")

    formatters = {
        'CSV_formatter': None,
        'HTML_formatter': AccountStatusActionReportHTMLFormatter,
    }

    def generate(self):
        accounts_status = AccountStatus.objects.prefetch_related(
            'auth_documents').select_related('profile', 'profile__user').filter(
            verification_status=AccountStatus.VERIFICATION_IN_PROGRESS).order_by(
            '-date_created')

        additional_data = {
            'start_date': self.start_date,
            'end_date': self.end_date
        }

        return self.formatter.generate_response(accounts_status, **additional_data)

    def is_available_to(self, user):
        return user.is_staff


class UserROIReportHTMLFormatter(ReportHTMLFormatter):
    filename_template = 'dashboard/reports/partials/users_roi_report.html'

class UserROIReportGenerator(ReportGenerator):
    """
    Report of paid packages
    """
    code = 'user_roi'
    description = 'Users ROI'

    formatters = {
        'CSV_formatter': None,
        'HTML_formatter': UserROIReportHTMLFormatter
    }

    def generate(self):
        additional_data = {
            'start_date': self.start_date,
            'end_date': self.end_date
        }
        report = []
        qs = User.objects.all()\
                .prefetch_related('orders__sources', 'orders')\
                .filter(is_active=True)\

        for user in qs:
            total_revenue = D('0.0')
            orders_num = 0
            for order in user.orders.all():
                if order.status not in ['Refunded', 'Cancelled']:
                    orders_num += 1
                    for source in order.sources.all():
                        total_revenue += source.self_revenue()
            if orders_num > 0:
                report.append({
                    'id': user.id,
                    'name': user.get_full_name(),
                    'email': user.email,
                    'total_revenues': total_revenue,
                    'average_revenue': (total_revenue / D(orders_num)).quantize(D('0.01')),
                    'num_orders': orders_num
                })

        report.sort(key=itemgetter('total_revenues'), reverse=True)
        return self.formatter.generate_response(report, **additional_data)

    def report_context_data(self, qs):
        return {
            'total_average_roi': (sum(item['average_revenue'] for item in qs) / D(len(qs))).quantize(D('0.01'))
        }

    def is_available_to(self, user):
        return user.is_staff