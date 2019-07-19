from django.core.management.base import BaseCommand
from django.utils.translation import ugettext as _
from django.conf import settings
from django.db.models import get_model
from django.db.models import Q

Profile = get_model('user', 'Profile')


class Command(BaseCommand):
    """
    Check for packages with 3 days before storage fee applied and alert the user
    have registered for an alert.
    """
    help = _("Reset remaining referrals invites to the default value")

    def handle(self, verbosity, **options):
        """
        reset daily invites quota for all customers (non staff, partner related users and inactive users)
        """

        #Get all users profiles, excluding staff, partner related users or inactive users
        profiles = Profile.objects.exclude(
            Q(user__is_staff=True) |
            Q(user__partners__isnull=False) |
            Q(user__is_active=False))

        profiles.update(remaining_invites=settings.DAILY_REFERRAL_INVITES_QUOTA)



