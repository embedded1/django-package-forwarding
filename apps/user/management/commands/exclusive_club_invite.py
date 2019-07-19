from django.utils.translation import ugettext as _
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from datetime import datetime, timedelta
from optparse import make_option
import logging


logger = logging.getLogger("management_commands")

class Command(BaseCommand):
    help = _("Send exclusive club invitations")
    option_list = BaseCommand.option_list + (
        make_option('-c', '--club_name', type='str',
            help="Club name"),
    )

    def handle(self, verbosity, club_name, **options):
        """
        Send exclusive club invitations
        Need to start on 10/14/2017
        """
        from apps.customer.alerts.senders import send_exclusive_club_email
        cutoff_date = datetime(2017, 10, 12, 0, 0, 0)
        now = datetime.now()
        now = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if now < cutoff_date:
            return

        start_range = now - timedelta(days=1)
        end_range = start_range + timedelta(hours=23, minutes=59, seconds=59)
        qualified_users = User.objects\
            .select_related('profile')\
            .filter(is_active=True, date_joined__range=(start_range, end_range))


        for user in qualified_users:
            profile = user.get_profile()
            qualified_exclusive_club = profile.get_exclusive_club()
            if qualified_exclusive_club and qualified_exclusive_club.lower() == club_name.lower():
                send_exclusive_club_email(user, club_name)


