from django.db.models import get_model
from oscar.core.loading import get_class
from datetime import datetime, timedelta
from django.utils.translation import ugettext_lazy as _
from django.db import connection
from django.db.models import Count
import logging

ReportGenerator = get_class('dashboard.reports.reports', 'ReportGenerator')
ReportCSVFormatter = get_class('dashboard.reports.reports', 'ReportCSVFormatter')
FilterPackageByPartner = get_class('dashboard.reports.mixins', 'FilterPackageByPartner')
ReportHTMLFormatter = get_class('dashboard.reports.reports', 'ReportHTMLFormatter')

Product = get_model('catalogue', 'Product')
AdditionalPackageReceiver = get_model('catalogue', 'AdditionalPackageReceiver')

logger = logging.getLogger(__name__)


class PackagesToConsolidateReportCSVFormatter(ReportCSVFormatter):
    filename_template = 'packages-to-consolidate-%s-%s.csv'

    def generate_csv(self, response, packages):
        writer = self.get_csv_writer(response)
        header_row = [
            'Customer suite number',
            'Customer name',
            'Consolidated Package Unique ID',
            'Unique IDs of packages to consolidate'
        ]
        writer.writerow(header_row)

        for package in packages:
            row = [
                package.owner.get_profile().uuid,
                package.owner,
                package.upc,
                u", ".join([p.upc for p in package.combined_products.all()])
            ]
            writer.writerow(row)

    def filename(self, **kwargs):
        return self.filename_template % (kwargs['start_date'],
                                         kwargs['end_date'])


class PackagesToConsolidateReportHTMLFormatter(ReportHTMLFormatter):
    filename_template = 'dashboard/reports/partials/consolidated_package_report.html'


class PackagesToConsolidateReportGenerator(ReportGenerator, FilterPackageByPartner):
    """
    Report of paid packages
    """
    code = 'consolidated_packages'
    description = 'Packages to consolidate'
    message = "Below you will find packages that need to be merged into 1 shipment.<br/>" \
              "Move items from selected packages into one of our predefined boxes. <br/>" \
              "Please pay attention to packing options - you may need to remove retail packing based on" \
              " cutomer's request. <br/>" \
              "Click on the enter master box properties button to update master box dimensions and weight.<br/>" \
              "Please inform your manager if items don't fit into 1 master box before taking any further actions."

    formatters = {
        'CSV_formatter': PackagesToConsolidateReportCSVFormatter,
        'HTML_formatter': PackagesToConsolidateReportHTMLFormatter}

    def generate(self):
        additional_data = {
            'start_date': self.start_date,
            'end_date': self.end_date
        }
        partner_packages = self.filter_by_partner()
        consolidated_packages = partner_packages.select_related(
            'owner', 'owner__profile', 'consolidation_requests', 'special_requests').filter(
            status='consolidation_taking_place').prefetch_related(
            'combined_products', 'stockrecords', 'stockrecords__partner').order_by(
            '-special_requests__express_checkout_done', 'consolidation_requests__date_created',
            'owner__profile__uuid', 'upc')
        return self.formatter.generate_response(consolidated_packages, **additional_data)

    def is_available_to(self, user):
        return user.is_staff or user.has_perm('partner.dashboard_access') or user.has_perm('partner.support_access')

class PackageSpecialRequestsReportCSVFormatter(ReportCSVFormatter):
    filename_template = 'packages-special-requests-%s-%s.csv'

    def generate_csv(self, response, packages):
        writer = self.get_csv_writer(response)
        header_row = ['Customer suite number'
                      'Customer name',
                      'Package unique ID',
                      'Pending special Requests']
        writer.writerow(header_row)

        for package in packages:
            row = [package.owner.get_profile().uuid,
                   package.owner.get_full_name(),
                   package.upc,
                   package.pending_special_requests_summary()]

            writer.writerow(row)

    def filename(self, **kwargs):
        return self.filename_template % (kwargs['start_date'],
                                         kwargs['end_date'])


class PackageSpecialRequestsReportHTMLFormatter(ReportHTMLFormatter):
    filename_template = 'dashboard/reports/partials/package_special_requests_report.html'


class PackageSpecialRequestsReportGenerator(ReportGenerator, FilterPackageByPartner):
    """
    Report of paid packages
    """
    code = 'packages_special_requests'
    description = 'Pending extra services'
    message = "Below you will find packages that extra services were ordered for them.<br/>" \
              "Click on the update button next to each package to complete the process."

    formatters = {
        'CSV_formatter': PackageSpecialRequestsReportCSVFormatter,
        'HTML_formatter': PackageSpecialRequestsReportHTMLFormatter}

    def generate(self):
        additional_data = {
            'start_date': self.start_date,
            'end_date': self.end_date
        }
        partner_packages = self.filter_by_partner()
        paid_packages = partner_packages.select_related(
            'owner', 'owner__profile', 'special_requests').prefetch_related(
            'stockrecords', 'stockrecords__partner').filter(
             status='handling_special_requests').order_by(
            '-special_requests__express_checkout_done', 'special_requests__date_updated',
            'owner__profile__uuid', 'upc')
        return self.formatter.generate_response(paid_packages, **additional_data)

    def is_available_to(self, user):
        return user.is_staff or user.has_perm('partner.dashboard_access') or user.has_perm('partner.support_access')



class PackageWaitingTimeForShipmentReportHTMLFormatter(ReportHTMLFormatter):
    filename_template = 'dashboard/reports/partials/package_dispatch.html'


class PackageWaitingTimeForShipmentReportCSVFormatter(ReportCSVFormatter):
    filename_template = 'package-dispatch-%s-%s.csv'

    def generate_csv(self, response, packages):
        writer = self.get_csv_writer(response)
        header_row = ['Package Unique ID', 'Postage Purchased Date']
        writer.writerow(header_row)

        for package in packages:
            row = [package.upc,
                   package.date_updated]
            writer.writerow(row)

    def filename(self, **kwargs):
        return self.filename_template % (kwargs['start_date'],
                                         kwargs['end_date'])


class PackageWaitingTimeForShipmentReportGenerator(ReportGenerator):
    """
    Report of paid packages
    """
    code = 'package_waiting_time_for_shipping'
    description = 'Package waiting time for shipping'

    formatters = {
        'CSV_formatter': PackageWaitingTimeForShipmentReportCSVFormatter,
        'HTML_formatter': PackageWaitingTimeForShipmentReportHTMLFormatter
    }

    def generate(self):
        now = datetime.now()
        additional_data = {
            'start_date': self.start_date,
            'end_date': self.end_date
        }
        two_days_ago = now - timedelta(days=2)
        packages_waiting_for_shipment = Product._default_manager.filter(
            status='postage_purchased', date_updated__lte=two_days_ago).order_by('date_updated')
        return self.formatter.generate_response(packages_waiting_for_shipment, **additional_data)


class AdditionalReceiverActionReportHTMLFormatter(ReportHTMLFormatter):
    filename_template = 'dashboard/reports/partials/additional_receiver_report.html'


class AdditionalReceiverActionReportGenerator(ReportGenerator):
    code = 'additional_receivers_verification_report'
    description = _("Additional receivers waiting for verification")

    formatters = {
        'CSV_formatter': None,
        'HTML_formatter': AdditionalReceiverActionReportHTMLFormatter,
    }

    def generate(self):
        additional_receivers = AdditionalPackageReceiver.objects.select_related(
            'package_owner').prefetch_related('documents').filter(
            verification_status=AdditionalPackageReceiver.VERIFICATION_IN_PROGRESS).order_by(
            '-date_created')

        additional_data = {
            'start_date': self.start_date,
            'end_date': self.end_date
        }

        return self.formatter.generate_response(additional_receivers, **additional_data)

    def is_available_to(self, user):
        return user.is_staff

class PackagesInWarehouseReportHTMLFormatter(ReportHTMLFormatter):
    filename_template = 'dashboard/reports/partials/packages_in_warehouse_report.html'


class PackagesInWarehouseReportCSVFormatter(ReportCSVFormatter):
    filename_template = 'packages-in-warehouse-%s-%s.csv'

    def generate_csv(self, response, packages):
        writer = self.get_csv_writer(response)
        header_row = [
            'Customer suite number',
            'Customer name',
            'Active account?',
            'Package unique ID',
            'Consolidated?',
            'Number of days after consolidation completed',
            'Number of days in storage',
        ]
        writer.writerow(header_row)

        for package in packages:
            post_consolidation_days = package.get_post_consolidation_days()
            row = [
                package.owner.get_profile().uuid,
                package.owner,
                'yes' if package.owner.is_active else 'no',
                package.upc,
                'yes' if package.is_consolidated else 'no',
                post_consolidation_days if package.is_consolidated and package.date_consolidated else '-',
                package.get_storage_days(),
            ]

            writer.writerow(row)

    def filename(self, **kwargs):
        return self.filename_template % (kwargs['start_date'],
                                         kwargs['end_date'])


class PackagesInWarehouseReportGenerator(ReportGenerator, FilterPackageByPartner):
    code = 'packages_in_warehouse_report'
    description = _("Packages currently in warehouse")

    formatters = {
        'CSV_formatter': PackagesInWarehouseReportCSVFormatter,
        'HTML_formatter': PackagesInWarehouseReportHTMLFormatter,
    }

    def generate(self):
        additional_data = {
            'start_date': self.start_date,
            'end_date': self.end_date
        }
        in_store_partner_packages = self.filter_in_store_packages_by_partner()\
            .order_by('date_created')

        return self.formatter.generate_response(in_store_partner_packages, **additional_data)

    def is_available_to(self, user):
        return user.is_staff or user.has_perm('partner.dashboard_access') or user.has_perm('partner.support_access')

class DiscardedPackagesReportHTMLFormatter(ReportHTMLFormatter):
    filename_template = 'dashboard/reports/partials/discarded_packages_report.html'

class DiscardedPackagesReportCSVFormatter(ReportCSVFormatter):
    filename_template = 'discarded-packages-%s-%s.csv'

    def generate_csv(self, response, packages):
        writer = self.get_csv_writer(response)
        header_row = [
            'Package ID',
            'Customer name',
            'USH number',
            'Number of days in storage',
            'Date entered into system',
            'Date discarded'
        ]
        writer.writerow(header_row)

        for package in packages:
            row = [
                package.upc,
                package.owner,
                package.owner.get_profile().uuid,
                package.get_storage_days(),
                package.date_created,
                package.date_updated
            ]
            writer.writerow(row)

    def filename(self, **kwargs):
        return self.filename_template % (kwargs['start_date'],
                                         kwargs['end_date'])

class DiscardedPackagesReportGenerator(ReportGenerator, FilterPackageByPartner):
    code = 'discarded_packages_report'
    description = _("Discarded Packages")

    formatters = {
        'CSV_formatter': DiscardedPackagesReportCSVFormatter,
        'HTML_formatter': DiscardedPackagesReportHTMLFormatter,
    }

    def generate(self):
        additional_data = {
            'start_date': self.start_date,
            'end_date': self.end_date
        }
        discarded_packages = self.filter_by_partner()\
            .filter(status='discarded')\
            .order_by('date_created')

        return self.formatter.generate_response(discarded_packages, **additional_data)

    def is_available_to(self, user):
        return user.is_staff or user.has_perm('partner.dashboard_access') or user.has_perm('partner.support_access')

class PackagesBreakdownReportHTMLFormatter(ReportHTMLFormatter):
    filename_template = 'dashboard/reports/partials/packages_breakdown.html'


class PackagesBreakdownReportGenerator(ReportGenerator):
    """
    Report of paid packages
    """
    code = 'packages_breakdown'
    description = 'Packages Breakdown'

    formatters = {
        'CSV_formatter': None,
        'HTML_formatter': PackagesBreakdownReportHTMLFormatter
    }

    def generate(self):
        additional_data = {
            'start_date': self.start_date,
            'end_date': self.end_date
        }
        truncate_date = connection.ops.date_trunc_sql('month', 'date_created')
        qs = Product.packages.all()\
                .exclude(combined_products__isnull=False)\
                .filter(date_created__range=(self.start_date, self.end_date))
        report = qs.extra({'month': truncate_date})\
            .values('month')\
            .annotate(num_packages=Count('pk'))\
            .order_by('month')
        return self.formatter.generate_response(report, **additional_data)


    def is_available_to(self, user):
        return user.is_staff


class PackagesWeightBreakdownReportHTMLFormatter(ReportHTMLFormatter):
    filename_template = 'dashboard/reports/partials/packages_weight_breakdown.html'


class PackagesWeightBreakdownReportGenerator(ReportGenerator):
    """
    Report of paid packages
    """
    code = 'packages_weight_breakdown'
    description = 'Packages Weight Breakdown'

    formatters = {
        'CSV_formatter': None,
        'HTML_formatter': PackagesWeightBreakdownReportHTMLFormatter
    }

    def generate(self):
        additional_data = {
            'start_date': self.start_date,
            'end_date': self.end_date
        }
        truncate_date = connection.ops.date_trunc_sql('month', 'date_placed')
        #qs = Order.objects.all()\
        #        .exclude(status__in=['Pending', 'Cancelled', 'Refunded'])\
        #        .filter(date_placed__range=(self.start_date, self.end_date))
        #report = qs.extra({'month': truncate_date})\
        #    .values('month')\
        #    .annotate(total_payments=Sum('total_incl_tax'), num_orders=Count('pk'))\
        #    .order_by('month')
        #return self.formatter.generate_response(report, **additional_data)


    def is_available_to(self, user):
        return user.is_staff