from apps.payment.sources.bitcoin.models import BitcoinTransaction, PaymentMessage
from apps.payment.sources.bitcoinpay.managers import BitcoinPayTransactionManager, BitcoinPayPaymentMessagenManager
from django.conf import settings


class BitcoinPayTransaction(BitcoinTransaction):
    objects = BitcoinPayTransactionManager()
    class Meta:
        proxy = True

    def save(self, force_insert=False, force_update=False, using=None):
        self.source = settings.BITCOIN_PAY_LABEL
        return super(BitcoinPayTransaction, self).save(force_insert, force_update, using)

class BitcoinPayPaymentMessage(PaymentMessage):
    objects = BitcoinPayPaymentMessagenManager()
    class Meta:
        proxy = True

    def save(self, force_insert=False, force_update=False, using=None):
        self.source = settings.BITCOIN_PAY_LABEL
        return super(BitcoinPayPaymentMessage, self).save(force_insert, force_update, using)