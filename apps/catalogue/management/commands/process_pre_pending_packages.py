from django.utils.translation import ugettext as _
from django.core.management.base import BaseCommand
from datetime import datetime, timedelta
from django.conf import settings
from django.db.models import get_model
from oscar.core.loading import get_class
from apps.catalogue.signals import product_status_change_alert
from optparse import make_option
import logging


Product = get_model('catalogue', 'Product')
Dispatcher = get_class('customer.utils', 'Dispatcher')
logger = logging.getLogger("management_commands")

class Command(BaseCommand):
    """
    Check for packages with 3 days before storage fee applied and alert the user
    have registered for an alert.
    """
    help = _("update pre_pending packages")
    option_list = BaseCommand.option_list + (
        make_option('-p', '--packages', type='string', default='',
            help="Enter comma separated packages to be updated"),
    )


    def send_package_updated_in_account_email(self, package):
        product_status_change_alert.send(
            sender=Product,
            customer=package.owner,
            package=package,
            extra_msg=None)

    def handle(self, verbosity, packages, **options):
        """
        Check all packages that have 3 days left to free storage and alert the customer
        Regular packages have 10 free days and consolidated packages have 30 free days
        therefore we separate both cases
        """
        if packages:
            pre_pending_packages_in_range = Product.objects\
                .select_related('owner')\
                .exclude(owner__is_active=False)\
                .filter(upc__in=packages.split(','), status='pre_pending')
        else:
            pre_pending_delay = getattr(settings, 'PRE_PENDING_DELAY_IN_DAYS', 1)

            #get all pre_pending packages (exclude packages of inactive users)
            pre_pending_packages = Product.objects.select_related(
                'owner').exclude(owner__is_active=False).filter(status='pre_pending')

            now = datetime.now()
            #get only year month and day
            now = now.replace(hour=0, minute=0, second=0, microsecond=0)

            start_date = now - timedelta(days=pre_pending_delay)
            end_date = start_date + timedelta(days=1, hours=23, minutes=59, seconds=59)

            pre_pending_packages_in_range = pre_pending_packages\
                .filter(date_created__range=(start_date, end_date))

        for package in pre_pending_packages_in_range:
            logger.info("Changed package #%s status to pending" % package.upc)
            #change status to pending or to predefined_waiting_for_consolidation
            #based on user's settings
            if package.owner.get_profile().is_predefined_consolidation():
                package.status = 'predefined_waiting_for_consolidation'
            else:
                package.status = 'pending'
            package.save()
            self.send_package_updated_in_account_email(package)






