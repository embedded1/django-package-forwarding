from django.utils.translation import ugettext as _
from django.core.management.base import BaseCommand
from django.db.models import get_model
from django.db.models import Q
import csv


User = get_model('auth', 'User')

class Command(BaseCommand):
    """
    Check for packages with 3 days before storage fee applied and alert the user
    have registered for an alert.
    """
    help = _("Dump all active users into a csv file")

    def handle(self, verbosity,  **options):
        """
        Send warehouse migration email to all customers (non staff and partner related users)
        """
        out_csv = 'all_active_users.csv'
        #Get all users, excluding staff, partner related users or inactive users
        all_users = User.objects.exclude(
            Q(is_staff=True) |
            Q(partners__isnull=False) |
            Q(is_active=False) |
            Q(email__in=['yanivkoter@gmail.com']))

        with open(out_csv, 'w') as csvfile:
            fieldnames = ['email', 'first_name', 'last_name']
            data_writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            data_writer.writeheader()
            for user in all_users:
                data_writer.writerow({
                    'email': user.email,
                    'first_name': user.first_name.encode('utf-8'),
                    'last_name': user.last_name.encode('utf-8'),
                })

