import datetime
from optparse import make_option
from apps.order.models import Order
from django.core.management.base import BaseCommand
from apps.rewards.models import ReferralReward
try:
    from django.utils.timezone import now
    now = now
except ImportError:
    now = datetime.now


class Command(BaseCommand):
    help = 'Place deferred messages back in the queue.'
    option_list = BaseCommand.option_list + (
        make_option('-d', '--days', type='int', default=3,
            help="Cleanup zombie orders older than this many days, defaults to 3."),
    )

    def handle(self, verbosity, days, **options):
        # Delete zombie orders and their related objects after X days
        cutoff_date = now() - datetime.timedelta(days)
        zombie_orders = Order.objects\
            .filter(status='Pending',
                    date_placed__lt=cutoff_date)
        count = zombie_orders.count()
        ReferralReward.objects\
            .filter(order__in=zombie_orders,
                    is_active=True,
                    date_redeemed__isnull=False)\
            .update(date_redeemed=None)
        zombie_orders.delete()
        print("Deleted {0} orders created before {1} ".format(count, cutoff_date))
