from django.db import models
from django.conf import settings


class BitcoinPayTransactionManager(models.Manager):
    def get_query_set(self):
        return super(BitcoinPayTransactionManager, self)\
            .get_query_set().filter(source=settings.BITCOIN_PAY_LABEL)


class BitcoinPayPaymentMessagenManager(models.Manager):
    def get_query_set(self):
        return super(BitcoinPayPaymentMessagenManager, self)\
            .get_query_set().filter(source=settings.BITCOIN_PAY_LABEL)