from oscar.apps.dashboard.views import IndexView as CoreIndexView
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from decimal import Decimal as D
from apps.catalogue.models import Product, AdditionalPackageReceiver
from apps.user.models import AccountStatus
from apps.order.utils import orders_ready_for_delivery
from django.contrib.auth.models import User
from datetime import datetime, timedelta
from apps.order.models import Order, ShippingLabelBatch
from apps.static.models import Statistics
from django.db.models import Count
from django.db.models import Q

class IndexView(CoreIndexView):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff and request.user.has_perm('partner.support_access'):
            return HttpResponseRedirect(reverse('dashboard:users-index'))
        return super(IndexView, self).dispatch(request, *args, **kwargs)


    def get_template_names(self):
        if self.request.user.is_staff:
            return ['dashboard/index.html']
        if self.request.user.has_perm('partner.support_access'):
            return ['dashboard/index_customer_support.html']
        else:
            return ['dashboard/index.html']

    def get_context_data(self, **kwargs):
        ctx = super(IndexView, self).get_context_data(**kwargs)
        if self.request.GET.get('staff_stats', '0') == '1':
            ctx['staff_stats_available'] = True
            ctx.update(self.get_staff_stats())
        ctx.update(self.get_reports_stats())
        if self.request.user.is_superuser:
            ctx.update(self.get_purse_users_stats())
        #count only packages as products
        ctx['total_products'] = Product.packages.by_partner_user(
            self.request.user).count()
        #total received packages (non including consolidated packages)
        ctx['total_received_packages'] = Product\
            .packages.by_partner_user(self.request.user)\
            .exclude(combined_products__isnull=False)\
            .count()
        ctx['total_consolidated_packages'] = Product\
            .packages.by_partner_user(self.request.user)\
            .filter(combined_products__isnull=False)\
            .distinct()\
            .count()
        #exclude staff or partner related users
        ctx['total_customers'] = User.objects.exclude(
            Q(is_staff=True) | Q(partners__isnull=False) | Q(is_active=False)).count()
        #exclude refunded and cancelled orders
        ctx['total_orders'] = Order.objects\
            .exclude(status__in=('Cancelled', 'Refunded', 'Pending'))\
            .count()
        return ctx


    def get_staff_stats(self):
        stats = {}
        #time_threshold = datetime.now() - timedelta(hours=2)
        if self.request.user.is_staff:
            try:
                chrome_counter = Statistics.objects.get(name='chrome').usage_counter
            except Statistics.DoesNotExist:
                chrome_counter = 0
            stats['chrome_extension_usage_count'] = chrome_counter
            stats['total_pending_packages'] = Product.packages.filter(
                status__in=['pending', 'predefined_waiting_for_consolidation',
                            'waiting_for_consolidation', 'pre_pending',
                            'pending_returned_package']).count()
            stats['total_orders_pending_fraud_check'] = Order.objects.filter(
                status='Pending fraud check',
                user__profile__account_status__verification_status="Verified").count()
            stats['total_active_customers'] = User.objects\
                .filter(packages__isnull=False, is_active=True).distinct().count()
            stats['total_customers_with_no_order'] = User.objects\
                .filter(packages__isnull=False, is_active=True)\
                .annotate(num_orders=Count('orders'))\
                .filter(num_orders=0).distinct().count()
            stats['total_customers_with_one_order'] = User.objects\
                .filter(is_active=True)\
                .exclude(orders__status__in=['Pending', 'Cancelled', 'Refunded'])\
                .annotate(num_orders=Count('orders'))\
                .filter(num_orders=1).distinct().count()
            stats['total_customers_with_more_than_one_order'] = User.objects\
                .filter(is_active=True)\
                .exclude(orders__status__in=['Pending', 'Cancelled', 'Refunded'])\
                .annotate(num_orders=Count('orders'))\
                .filter(num_orders__gt=1).distinct().count()
        return stats

    def get_reports_stats(self):
        user = self.request.user
        total_packages_waiting_for_extra_services = Product.packages.by_partner_user(user).filter(
            status='handling_special_requests').count()
        total_new_consolidated_packages = Product.packages.by_partner_user(user).filter(
            status='consolidation_taking_place').count()
        #total_package_waiting_for_take_measures =  Product._default_manager.filter(
        #    status='take_measures').count()
        orders_waiting_for_shipping_label = []
        all_orders_waiting_for_shipping_label = Order\
            ._default_manager\
            .prefetch_related('user__orders')\
            .filter(status='In process')
        if not user.is_staff:
            all_orders_waiting_for_shipping_label = all_orders_waiting_for_shipping_label\
                .filter(package__stockrecords__partner__users=user)
        orders_waiting_for_shipping_label = orders_ready_for_delivery(all_orders_waiting_for_shipping_label)
        total_orders_waiting_for_shipping_label = len(orders_waiting_for_shipping_label)
        orders_ready_to_be_shipped = ShippingLabelBatch._default_manager.filter(
            status=ShippingLabelBatch.STATUS.label_generated)
        if not user.is_staff:
            orders_ready_to_be_shipped = orders_ready_to_be_shipped.filter(partner__users=user)
        total_orders_ready_to_be_shipped = orders_ready_to_be_shipped.aggregate(
            num_orders=Count('orders'))['num_orders']
        orders_with_prepaid_return_label = Order._default_manager.filter(
            status='Wait for return label download')
        if not user.is_staff:
            orders_with_prepaid_return_label = orders_with_prepaid_return_label.filter(
                 package__stockrecords__partner__users=user)
        total_orders_with_prepaid_return_label = orders_with_prepaid_return_label.count()

        stats = {
            'total_packages_waiting_for_extra_services': total_packages_waiting_for_extra_services,
            'total_new_consolidated_packages': total_new_consolidated_packages,
            #'total_package_waiting_for_take_measures': total_package_waiting_for_take_measures,
            'total_orders_waiting_for_shipping_label': total_orders_waiting_for_shipping_label,
            'total_orders_ready_to_be_shipped': total_orders_ready_to_be_shipped,
            'total_orders_with_prepaid_return_label': total_orders_with_prepaid_return_label,
        }

        if self.request.user.is_staff:
            stats['total_accounts_pending_verification'] = AccountStatus.objects.filter(
                    verification_status=AccountStatus.VERIFICATION_IN_PROGRESS).count()
            stats['total_additional_receivers_pending_verification'] = AdditionalPackageReceiver.objects.filter(
                    verification_status=AccountStatus.VERIFICATION_IN_PROGRESS).count()
        return stats

    def get_purse_users_stats(self):
        TWOPLACES = D(10) ** -2
        purse_users = User.objects.filter(profile__registration_type='purse', is_active=True)
        total_purse_users = purse_users.count()
        total_purse_users_with_confirmed_email = purse_users.filter(profile__email_confirmed=True).count()
        total_purse_users_with_unconfirmed_email = total_purse_users - total_purse_users_with_confirmed_email
        total_purse_users_with_order = purse_users.annotate(num_orders=Count('orders'))\
            .filter(num_orders__gt=0).distinct().count()
        total_purse_users_with_no_order = total_purse_users - total_purse_users_with_order
        total_purse_users_with_packages = purse_users.filter(packages__isnull=False).distinct().count()
        total_purse_users_with_no_packages = total_purse_users - total_purse_users_with_packages

        purse_stats = {
            'total_purse_users': total_purse_users,
            'total_purse_users_with_confirmed_email': total_purse_users_with_confirmed_email,
            'confirmed_email_ratio': ((D(total_purse_users_with_confirmed_email) / D(total_purse_users)) * 100).quantize(TWOPLACES) if total_purse_users > 0 else 0,
            'total_purse_users_with_unconfirmed_email': total_purse_users_with_unconfirmed_email,
            'unconfirmed_email_ratio': ((D(total_purse_users_with_unconfirmed_email) / D(total_purse_users)) * 100).quantize(TWOPLACES) if total_purse_users > 0 else 0,
            'total_purse_users_with_order': total_purse_users_with_order,
            'orders_ratio': ((D(total_purse_users_with_order) / D(total_purse_users)) * 100).quantize(TWOPLACES) if total_purse_users > 0 else 0,
            'total_purse_users_with_no_order': total_purse_users_with_no_order,
            'no_orders_ratio': ((D(total_purse_users_with_no_order) / D(total_purse_users)) * 100).quantize(TWOPLACES) if total_purse_users > 0 else 0,
            'total_purse_users_with_packages': total_purse_users_with_packages,
            'packages_ratio': ((D(total_purse_users_with_packages) / D(total_purse_users)) * 100).quantize(TWOPLACES) if total_purse_users > 0 else 0,
            'total_purse_users_without_packages': total_purse_users_with_no_packages,
            'no_packages_ratio': ((D(total_purse_users_with_no_packages) / D(total_purse_users)) * 100).quantize(TWOPLACES) if total_purse_users > 0 else 0,
        }

        return purse_stats



