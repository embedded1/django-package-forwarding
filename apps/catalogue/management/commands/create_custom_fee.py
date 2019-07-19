from django.db.models import get_model
from django.conf import settings
from apps.catalogue.utils import create_fee
from decimal import Decimal as D
from django.core.management.base import BaseCommand
from django.utils.translation import ugettext as _
from optparse import make_option

Product = get_model('catalogue', 'Product')

class Command(BaseCommand):
    """
    Create custom fee and link to package
    """
    help = _("Create custom fee")
    option_list = BaseCommand.option_list + (
        make_option('-p', '--package_upc', type='string',
            help="Enter package upc"),
        make_option('-d', '--description', type='string',
            help="Enter charge description"),
        make_option('-c', '--charge', type='string',
            help="Enter fee charge"),
    )


    def handle(self, verbosity, package_upc, description, charge, **options):
        try:
            package = Product.objects.get(upc=package_upc)
        except Product.DoesNotExist:
            print "Package with upc = %s not found" % package_upc
        else:
            idx = package.variants.filter(status='fixed_fees').count()
            upc = settings.CUSTOM_FEE_TEMPLATE % (package.upc, idx)
            create_fee(
                upc=upc,
                title=description.title(),
                package=package,
                charge=D(charge),
                status='fixed_fees')








