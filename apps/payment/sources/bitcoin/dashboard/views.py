from django.views import generic
from .. import models


class TransactionListView(generic.ListView):
    model = models.BitsOfGoldTransaction
    template_name = 'bitcoin/dashboard/transaction_list.html'
    context_object_name = 'transactions'


class TransactionDetailView(generic.DetailView):
    model = models.BitsOfGoldTransaction
    template_name = 'bitcoin/dashboard/transaction_detail.html'
    context_object_name = 'txn'


class PaymentsListView(generic.ListView):
    model = models.BitsOfGoldPaymentMessage
    template_name = 'bitcoin/ipn/dashboard/payment/messages_list.html'
    context_object_name = 'payment_messages'


class PaymentDetailView(generic.DetailView):
    model = models.BitsOfGoldPaymentMessage
    template_name = 'bitcoin/ipn/dashboard/payment/message_detail.html'
    context_object_name = 'payment_message'

