from django.utils.translation import ugettext as _
from django.core.management.base import BaseCommand
from django.db.models import get_model
from django.core.urlresolvers import reverse
from pinax.referrals.models import Referral
from django.db.models import Q
import logging


User = get_model('auth', 'User')
logger = logging.getLogger("management_commands")

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

        #Get all users, excluding inactive users
        users = User.objects.exclude(is_active=False)

        for user in users:
            referral = Referral.create(
                redirect_to=reverse('promotions:home'),
                user=user)
            profile = user.get_profile()
            profile.referral = referral
            profile.save()



