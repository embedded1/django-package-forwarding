from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from .managers import BitsOfGoldTransactionManager, BitsOfGoldPaymentMessagenManager
from paypal import base


class BitcoinTransaction(base.ResponseModel):
    # Request info
    is_sandbox = models.BooleanField(default=True)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True)
    amount_btc = models.DecimalField(
        max_digits=12, decimal_places=8, null=True, blank=True)
    currency = models.CharField(max_length=32, null=True, blank=True)
    # Only set if the transaction is successful.
    token = models.CharField(max_length=64, null=True, blank=True,
                               db_index=True)
    source = models.CharField(max_length=32, db_index=True)
    # Response info
    OK, FAILURE = 'ok', 'Failure'
    ack = models.CharField(max_length=32)

    class Meta:
        ordering = ('-date_created',)

    def __unicode__(self):
        return self.token

    @property
    def is_successful(self):
        return self.ack in (self.OK, )

    @property
    def redirect_url(self):
        return self.value('url') or self.value('payment_url')

class PaymentMessage(base.IPNMessageModel):
    payment_status = models.CharField(max_length=32, db_index=True)
    source = models.CharField(max_length=32, db_index=True)

    class Meta:
        ordering = ('-date_created',)
        verbose_name = _('Bitcoin IPN payment message')
        verbose_name_plural = _('Bitcoin IPN payment messages')

    def __unicode__(self):
        return self.transaction_id


class BitsOfGoldTransaction(BitcoinTransaction):
    objects = BitsOfGoldTransactionManager()
    class Meta:
        proxy = True

    def save(self, force_insert=False, force_update=False, using=None):
        self.source = settings.BITS_OF_GOLD_LABEL
        return super(BitsOfGoldTransaction, self).save(force_insert, force_update, using)

class BitsOfGoldPaymentMessage(PaymentMessage):
    objects = BitsOfGoldPaymentMessagenManager()
    class Meta:
        proxy = True

    def save(self, force_insert=False, force_update=False, using=None):
        self.source = settings.BITS_OF_GOLD_LABEL
        return super(BitsOfGoldPaymentMessage, self).save(force_insert, force_update, using)