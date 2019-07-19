from django.db.models import get_model
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.translation import ugettext as _
from apps.partner.utils import create_package_stock_record
from optparse import make_option


Partner = get_model('partner', 'Partner')
Product = get_model('catalogue', 'Product')


class Command(BaseCommand):
    """
    Check for packages with 3 days before storage fee applied and alert the user
    have registered for an alert.
    """
    help = _("Link all packages to partner")
    option_list = BaseCommand.option_list + (
        make_option('-p', '--partner_name', type='string', default=settings.ACTIVE_PARTNER_NAME,
            help="Enter partner's name or active partner name will be used"),
    )


    def handle(self, verbosity, partner_name, **options):
        partner = Partner.objects.get(name=partner_name)
        for package in Product.packages.all():
            create_package_stock_record(package=package, partner=partner)








