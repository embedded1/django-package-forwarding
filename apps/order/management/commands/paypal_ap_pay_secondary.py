from django.utils.translation import ugettext as _
from django.core.management.base import BaseCommand
from django.db.models import get_model
from paypal.adaptive.models import AdaptiveTransaction
from paypal.adaptive.facade import pay_secondary_receivers
from paypal import exceptions
from django.db.models import Q
import logging


Order = get_model('order', 'Order')
Source = get_model('payment', 'Source')
logger = logging.getLogger("management_commands")


class Command(BaseCommand):
    """
    Call PayPal adaptive payments ExecutePayment API to transfer the payment for the secondary
    receiver, we use delayed payment to make sure the order is legit before we transfer the money
    for the secondary receiver.
    """
    help = _("Pay logistics partner share")


    def handle(self, **options):
        """
        First we need to get PayPal Pay transaction id for all completed orders
        then we need to get all CREATED Pay translations
        that match the ids we retrieved above and that the amount_debited is greater than 0 which means
        we had a secondary receiver, then we use the pay keys to complete the secondary
        receiver payment and change the status to COMPLETED.

        =========================================================================================
        Currently this task only handles orders with prepaid return labels, for all other orders
        the payment is transferred right after the shipping label has been generated
        =========================================================================================
        """
        unpaid_pay_keys = []
        paypal_sources =(Source._default_manager.filter(
            Q(order__status='Pending partner payment') &
            Q(source_type__name='PayPal') &
            ~Q(reference='')))

        all_pay_keys = [s.reference for s in paypal_sources]
        paypal_created_pay_transactions = AdaptiveTransaction.objects.filter(
            payment_exec_status=AdaptiveTransaction.CREATED,
            pay_key__in=all_pay_keys)

        for created_pay_transaction in paypal_created_pay_transactions:
            pay_key = created_pay_transaction.pay_key
            try:
                pay_secondary_receivers(pay_key)
            except exceptions.PayPalError:
                logger.critical("Transfer payment for secondary receiver failed!, pay_key = %s" % pay_key)
                unpaid_pay_keys.append(pay_key)
            else:
                created_pay_transaction.payment_exec_status = AdaptiveTransaction.COMPLETED
                created_pay_transaction.save()

        #now we need to update orders that we managed to transfer partner payments
        #or change status direcly to Shipped for order with prepaid return label
        paid_paypal_sources = paypal_sources.exclude(reference__in=unpaid_pay_keys)
        for source in paid_paypal_sources:
            order = source.order
            order.set_status('Shipped')
            #mark that partner was fully paid
            source.partner_paid = True
            source.save()