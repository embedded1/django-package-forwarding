import datetime
from optparse import make_option
from apps.order.models import ShippingLabelBatch
from django.core.management.base import BaseCommand

try:
    from django.utils.timezone import now
    now = now
except ImportError:
    now = datetime.now


class Command(BaseCommand):
    help = 'Place deferred messages back in the queue.'
    option_list = BaseCommand.option_list + (
        make_option('-d', '--days', type='int', default=90,
            help="Cleanup batches older than this many days, defaults to 90."),
    )

    def handle(self, verbosity, days, **options):
        # Delete mails and their related logs and queued created before X days
        cutoff_date = now() - datetime.timedelta(days)
        count = ShippingLabelBatch.objects.filter(date_created__lt=cutoff_date).count()
        ShippingLabelBatch.objects.filter(date_created__lt=cutoff_date).delete()
        print("Deleted {0} batches created before {1} ".format(count, cutoff_date))
