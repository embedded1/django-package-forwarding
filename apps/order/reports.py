from django.db.models import get_model
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_class
from django.conf import settings
from .utils import orders_ready_for_delivery
from django.db import connection
from django.db.models import Count, Sum
from decimal import Decimal as D

ReportGenerator = get_class('dashboard.reports.reports',
                            'ReportGenerator')
ReportCSVFormatter = get_class('dashboard.reports.reports',
                               'ReportCSVFormatter')
ReportHTMLFormatter = get_class('dashboard.reports.reports',
                                'ReportHTMLFormatter')
FilterOrderByPartner = get_class('dashboard.reports.mixins',
                                 'FilterOrderByPartner')
Order = get_model('order', 'Order')
Partner = get_model('partner', 'Partner')
ShippingLabelBatch = get_model('order', 'ShippingLabelBatch')


class PackageReadyForShippingReportCSVFormatter(ReportCSVFormatter):
    filename_template = 'packages-ready-for-shipping-%s-%s.csv'

    def generate_csv(self, response, paid_orders):
        writer = self.get_csv_writer(response)
        header_row = [
            'Customer suite number',
            'Customer name',
            'Package unique ID',
            'Shipping method',
            'Customs declaration',
            'Shipping address',
            'Date placed',
            'Express checkout?'
        ]
        writer.writerow(header_row)

        for order in paid_orders:
            type, items = order.package.custom_form_summary
            customs_declaration = type + u" ,".join(items)
            is_express_checkout = "yes" if order.package.special_requests.is_express_checkout else "no"
            row = [order.user.get_profile.uuid,
                   order.user,
                   order.package.upc,
                   order.shipping_method,
                   customs_declaration,
                   order.shipping_address.summary,
                   order.date_placed,
                   is_express_checkout]

            writer.writerow(row)

    def filename(self, **kwargs):
        return self.filename_template % (kwargs['start_date'],
                                         kwargs['end_date'])


class PackageReadyForShippingReportHTMLFormatter(ReportHTMLFormatter):
    filename_template = 'dashboard/reports/partials/package_ready_for_shipping_report.html'


class PackageReadyForShippingReportGenerator(ReportGenerator, FilterOrderByPartner):
    """
    Report of paid packages
    """
    code = 'packages_ready_for_shipping_label'
    description = 'Orders waiting for shipping label'
    message = "This is the final step before purchasing shipping labels. <br/>" \
              "Therefore, this is the final step we can catch customs declaration errors.<br/>" \
              "Please review carefully each customs declaration below and select only orders that have " \
              "a complete and accurate customs declaration.<br/>" \
              "Please let your manager know about all orders that contain customs declaration errors.<br/>" \
              "Please gather all packages that are ready to be shipped and only when its done click on the" \
              " purchase shipping labels button to begin the purchasing process."


    formatters = {
        'CSV_formatter': PackageReadyForShippingReportCSVFormatter,
        'HTML_formatter': PackageReadyForShippingReportHTMLFormatter}

    def generate(self):
        """
        We only take orders that were not placed today, to make us some room catching bogus payments
        """
        additional_data = {
            'start_date': self.start_date,
            'end_date': self.end_date
        }

        partner_orders = self.filter_by_partner()
        all_awaiting_orders = partner_orders\
            .prefetch_related(
            'package__stockrecords',
            'package__stockrecords__partner',
            'user__orders')\
            .filter(status='In process')\
            .select_related(
            'user', 'user__profile', 'package', 'customs_form',
            'package__special_requests', 'tracking')\
            .order_by(
            '-package__special_requests__express_checkout_done',
            'date_placed', 'user__profile__uuid', 'package__upc')

        awaiting_orders = orders_ready_for_delivery(all_awaiting_orders)
        return self.formatter.generate_response(awaiting_orders, **additional_data)

    def is_available_to(self, user):
        return user.is_staff or user.has_perm('partner.dashboard_access') or user.has_perm('partner.support_access')


class PendingFraudCheckOrderReportCSVFormatter(ReportCSVFormatter):
    filename_template = 'pending-fraud_check_orders-%s-to-%s.csv'

    def generate_csv(self, response, orders):
        writer = self.get_csv_writer(response)
        header_row = [('Order number'),
                      ('Customer suite number'),
                      ('Customer name'),
                      ('Order total'),
                      ('Shipping address'),
                      ('Date placed')]
        writer.writerow(header_row)
        for order in orders:
            row = [order.number,
                   order.user.get_profile().uuid,
                   order.user,
                   order.total_incl_tax,
                   order.shipping_address.summary,
                   self.format_datetime(order.date_placed)]
            writer.writerow(row)

    def filename(self, **kwargs):
        return self.filename_template % (kwargs['start_date'], kwargs['end_date'])


class PendingFraudCheckOrderReportHTMLFormatter(ReportHTMLFormatter):
    filename_template = 'dashboard/reports/partials/pending_fraud_check_order_report.html'


class PendingFraudCheckOrderReportGenerator(ReportGenerator):
    code = 'pending_fraud_check_order_report'
    description = _("Orders pending proxy update")

    formatters = {
        'CSV_formatter': PendingFraudCheckOrderReportCSVFormatter,
        'HTML_formatter': PendingFraudCheckOrderReportHTMLFormatter,
    }

    def generate(self):
        orders = Order._default_manager\
            .select_related('user', 'user__profile',
                            'user__profile__account_status', 'shipping_address')\
            .filter(status='Pending fraud check',
                    user__profile__account_status__verification_status="Verified")\
            .order_by('-package__special_requests__express_checkout_done', 'date_placed')

        additional_data = {
            'start_date': self.start_date,
            'end_date': self.end_date
        }
        return self.formatter.generate_response(orders, **additional_data)

    def is_available_to(self, user):
        return user.is_staff


class PrintShippingLabelsReportHTMLFormatter(ReportHTMLFormatter):
    filename_template = 'dashboard/reports/partials/print_shipping_label.html'


class PrintShippingLabelsReportCSVFormatter(ReportCSVFormatter):
    filename_template = 'print-shipping-labels-%s-%s.csv'

    def generate_csv(self, response, batches):
        writer = self.get_csv_writer(response)
        header_row = ['Number of shipping labels', 'Purchase date']
        writer.writerow(header_row)

        for batch in batches:
            row = [batch.orders.all().count(),
                   batch.date_updated]
            writer.writerow(row)

    def filename(self, **kwargs):
        return self.filename_template % (kwargs['start_date'],
                                         kwargs['end_date'])


class PrintShippingLabelsReportGenerator(ReportGenerator):
    """
    Report of paid packages
    """
    code = 'print_shipping_labels'
    description = 'Print shipping labels'
    message = "Below you can find all purchased shipping labels, we purchase the labels in batches.<br/>" \
              "This means that each batch contains multiple labels. <br/>" \
              "On every shipping label you will find the private suite number and the package unique ID.<br/>" \
              "Use that information to locate the appropiate package.<br/>" \
              "First click on the Detect Printer button and then click on the Print button next to a batch" \
              " to print the labels.<br/>" \
              "Select all successfully printed batches and click on the Print job ended successfully button to" \
              "update DB."

    formatters = {
        'CSV_formatter': PrintShippingLabelsReportCSVFormatter,
        'HTML_formatter': PrintShippingLabelsReportHTMLFormatter
    }

    def generate(self):
        additional_data = {
            'start_date': self.start_date,
            'end_date': self.end_date
        }
        partner_shipping_labels = ShippingLabelBatch._default_manager.all().select_related('partner')
        #if user is not staff show only shipping labels that belong to partner
        if not self.user.is_staff:
            partner = Partner.objects.filter(users=self.user)
            partner_shipping_labels = partner_shipping_labels.filter(partner=partner)
        batches_with_generated_labels = partner_shipping_labels.prefetch_related('orders').filter(
            status=ShippingLabelBatch.STATUS.label_generated).order_by('-date_created')
        return self.formatter.generate_response(batches_with_generated_labels, **additional_data)

    def is_available_to(self, user):
        return user.is_staff or user.has_perm('partner.dashboard_access') or user.has_perm('partner.support_access')



class DownloadReturnLabelReportHTMLFormatter(ReportHTMLFormatter):
    filename_template = 'dashboard/reports/partials/download_return_labels.html'


class DownloadReturnLabelReportCSVFormatter(ReportCSVFormatter):
    filename_template = 'download-return-shipping-labels-%s-%s.csv'

    def generate_csv(self, response, orders):
        writer = self.get_csv_writer(response)
        header_row = ['Customer suite number', 'Customer name', 'Package unique ID',
                      'Date placed', 'Express checkout?']
        writer.writerow(header_row)

        for order in orders:
            row = [order.user.get_profile().uuid,
                   order.user,
                   order.package.upc,
                   order.date_placed,
                   order.package.special_requests.express_checkout_done]
            writer.writerow(row)

    def filename(self, **kwargs):
        return self.filename_template % (kwargs['start_date'],
                                         kwargs['end_date'])


class DownloadReturnLabelReportGenerator(ReportGenerator, FilterOrderByPartner):
    """
    Report of paid packages
    """
    code = 'download_return_label'
    description = 'Download return labels'
    message = "Below you can find all prepaid return labels.<br/>" \
              "Download return labels, print and apply them on the packages.<br/>" \
              "A folder that contains the package unique ID will be created for each return label for" \
              "package identification."

    formatters = {
        'CSV_formatter': DownloadReturnLabelReportCSVFormatter,
        'HTML_formatter': DownloadReturnLabelReportHTMLFormatter
    }

    def generate(self):
        additional_data = {
            'start_date': self.start_date,
            'end_date': self.end_date
        }
        partner_orders = self.filter_by_partner()
        prepaid_return_labels_orders = partner_orders.filter(
            status='Wait for return label download').select_related(
            'user', 'user__profile',
            'package', 'special_requests').order_by(
            '-package__special_requests__express_checkout_done',
            'date_placed', 'user__profile__uuid', 'package__upc'
        )
        return self.formatter.generate_response(prepaid_return_labels_orders, **additional_data)

    def is_available_to(self, user):
        return user.is_staff or user.has_perm('partner.dashboard_access') or user.has_perm('partner.support_access')

class PartnerPaymentsReportHTMLFormatter(ReportHTMLFormatter):
    filename_template = 'dashboard/reports/partials/partner_payments.html'


class PartnerPaymentsReportReportCSVFormatter(ReportCSVFormatter):
    filename_template = 'partner-payments-%s-%s.csv'

    def generate_csv(self, response, orders):
        writer = self.get_csv_writer(response)
        header_row = [
            'Package number',
            'Package receive date',
            'Name',
            'Order Number',
            'Shipping method',
            'Base shipping rate',
            'Shipping surcharges',
            'Tracking number',
            'Payment amount',
            'Fully paid?',
            'Payment type',
            'Payment date',
        ]
        writer.writerow(header_row)

        for order in orders:
            method = order.tracking.display_carrier + ' ' + order.shipping_method
            source = order.get_payment_source()
            row = [order.package.upc,
                   order.package.date_created,
                   order.user.get_full_name(),
                   order.number,
                   method if 'N/A' not in method else "Prepaid return label",
                   order.shipping_excl_tax,
                   order.shipping_surcharges or '-',
                   order.tracking.tracking_number or '-',
                   source.partner_share,
                   'yes' if source.partner_paid else 'no',
                   source.label,
                   order.date_placed]

            writer.writerow(row)

    def filename(self, **kwargs):
        return self.filename_template % (kwargs['start_date'],
                                         kwargs['end_date'])


class PartnerPaymentsReportReportGenerator(ReportGenerator, FilterOrderByPartner):
    """
    Report of paid packages
    """
    code = 'partner_payments'
    description = 'Partner Payments Report'

    formatters = {
        'CSV_formatter': PartnerPaymentsReportReportCSVFormatter,
        'HTML_formatter': PartnerPaymentsReportHTMLFormatter
    }

    def generate(self):
        additional_data = {
            'start_date': self.start_date,
            'end_date': self.end_date
        }
        partner_orders = self.filter_by_partner()\
        .select_related('package', 'tracking')\
        .prefetch_related('lines')\
        .exclude(status__in=['Pending', 'Cancelled', 'Refunded'])\
        .filter(date_placed__range=(self.start_date, self.end_date))\
        .order_by('-date_placed')
        return self.formatter.generate_response(partner_orders, **additional_data)

    def is_available_to(self, user):
        return user.is_staff or user.has_perm('partner.dashboard_access')

class PaymentsReportHTMLFormatter(ReportHTMLFormatter):
    filename_template = 'dashboard/reports/partials/payments.html'


class PaymentsReportReportCSVFormatter(ReportCSVFormatter):
    filename_template = 'download-return-shipping-labels-%s-%s.csv'

    def generate_csv(self, response, orders):
        pass

    def filename(self, **kwargs):
        return self.filename_template % (kwargs['start_date'],
                                         kwargs['end_date'])


class PaymentsReportReportGenerator(ReportGenerator):
    """
    Report of paid packages
    """
    code = 'payments'
    description = 'Payments Report'

    formatters = {
        'CSV_formatter': None,
        'HTML_formatter': PaymentsReportHTMLFormatter
    }

    def generate(self):
        additional_data = {
            'start_date': self.start_date,
            'end_date': self.end_date
        }
        orders = Order.objects.all()\
        .select_related('package', 'tracking')\
        .prefetch_related('lines', 'sources')\
        .exclude(status__in=['Pending', 'Cancelled', 'Refunded'])\
        .filter(date_placed__range=(self.start_date, self.end_date))\
        .order_by('-date_placed')
        return self.formatter.generate_response(orders, **additional_data)

    def report_context_data(self, qs):
        partner_bitcoin_payments = total_revenues = paypal_total_payments =\
        bitcoin_total_payments = partner_payments =\
        partner_shipping_costs = shipping_plus_insurance_costs = D('0.0')

        for order in list(qs):
            source = order.sources.all()[0]
            if source.source_type.name == "PayPal":
                paypal_total_payments += order.total_incl_tax
            else:
                bitcoin_total_payments += order.total_incl_tax
                partner_bitcoin_payments += source.partner_share
            total_revenues += source.self_revenue()
            partner_payments += source.partner_share
            if order.partner_paid_for_shipping():
                partner_shipping_costs += order.shipping_excl_tax
                shipping_plus_insurance_costs += order.shipping_insurance_excl_tax
            else:
                shipping_plus_insurance_costs += order.shipping_excl_tax + order.shipping_insurance_excl_tax

        num_orders = D(len(qs))
        average_payment = (total_revenues / num_orders).quantize(D('0.01'))\
            if num_orders > 0 else 0
        return {
            'paypal_total_payments': paypal_total_payments,
            'bitcoin_total_payments': bitcoin_total_payments,
            'total_payments': paypal_total_payments + bitcoin_total_payments,
            'total_revenues': total_revenues,
            'shipping_plus_insurance_costs': shipping_plus_insurance_costs,
            'partner_payments': partner_payments,
            'partner_bitcoin_payments': partner_bitcoin_payments,
            'partner_paypal_payments': partner_payments - partner_bitcoin_payments,
            'partner_shipping_costs': partner_shipping_costs,
            'average_payment': average_payment,
            'num_records': num_orders
        }

    def is_available_to(self, user):
        return user.is_staff


class OrdersBreakdownReportHTMLFormatter(ReportHTMLFormatter):
    filename_template = 'dashboard/reports/partials/orders_breakdown.html'


class OrdersBreakdownReportGenerator(ReportGenerator):
    """
    Report of paid packages
    """
    code = 'orders_breakdown'
    description = 'Orders Breakdown'

    formatters = {
        'CSV_formatter': None,
        'HTML_formatter': OrdersBreakdownReportHTMLFormatter
    }

    def generate(self):
        additional_data = {
            'start_date': self.start_date,
            'end_date': self.end_date
        }
        truncate_date = connection.ops.date_trunc_sql('month', 'date_placed')
        qs = Order.objects.all()\
                .exclude(status__in=['Pending', 'Cancelled', 'Refunded'])\
                .filter(date_placed__range=(self.start_date, self.end_date))
        report = qs.extra({'month': truncate_date})\
            .values('month')\
            .annotate(total_payments=Sum('total_incl_tax'), num_orders=Count('pk'))\
            .order_by('month')
        return self.formatter.generate_response(report, **additional_data)


    def is_available_to(self, user):
        return user.is_staff

class BitcoinPaymentsReportHTMLFormatter(ReportHTMLFormatter):
    filename_template = 'dashboard/reports/partials/bitcoin_payments.html'


class BitcoinPaymentsReportGenerator(ReportGenerator):
    """
    Report of paid packages
    """
    code = 'bitcoin_payments'
    description = 'Bitcoin Payments Report'

    formatters = {
        'CSV_formatter': None,
        'HTML_formatter': BitcoinPaymentsReportHTMLFormatter
    }

    def generate(self):
        additional_data = {
            'start_date': self.start_date,
            'end_date': self.end_date
        }
        orders = Order.objects\
        .prefetch_related('sources')\
        .exclude(status__in=['Pending', 'Cancelled', 'Refunded'])\
        .filter(sources__label='Bitcoin',
                date_placed__range=(self.start_date, self.end_date))\
        .order_by('-date_placed')
        return self.formatter.generate_response(orders, **additional_data)

    def report_context_data(self, qs):
        total_pending_payments = usendhome_pending_payments = \
        partner_pending_payments = D('0.0')

        for order in qs.filter(sources__amount_debited=0):
            source = order.sources.all()[0]
            total_pending_payments += source.amount_allocated
            usendhome_pending_payments += source.self_share
            if not source.partner_paid:
                partner_pending_payments += source.partner_share

        num_orders = D(qs.count())

        return {
            'total_pending_payments': total_pending_payments,
            'usendhome_pending_payments': usendhome_pending_payments,
            'partner_pending_payments': partner_pending_payments,
            'num_records': num_orders
        }

    def is_available_to(self, user):
        return user.is_staff
