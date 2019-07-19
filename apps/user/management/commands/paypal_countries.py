from django.utils.translation import ugettext as _
from django.core.management.base import BaseCommand
from apps.address.models import Country


class Command(BaseCommand):
    """
    Check for packages with 3 days before storage fee applied and alert the user
    have registered for an alert.
    """
    help = _("Give personal referral link to existing users")

    def handle(self, verbosity, **options):
        """
        Create a personal referral link for each existing user
        """
    all_countries = list(Country.objects.all())
    with open('/home/asi/paypal.txt') as f:
        for c in all_countries:
            f.seek(0)
            found = False
            for line in f:
                if c.name.lower() == line.strip().lower():
                    found = True
                    break
            if not found:
                print "%s-%s\n" % (c.printable_name, c.iso_3166_1_a2)

