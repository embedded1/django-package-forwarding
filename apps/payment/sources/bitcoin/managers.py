from django.db import models
from django.conf import settings


class BitsOfGoldTransactionManager(models.Manager):
    def get_query_set(self):
        return super(BitsOfGoldTransactionManager, self)\
            .get_query_set().filter(source=settings.BITS_OF_GOLD_LABEL)

class BitsOfGoldPaymentMessagenManager(models.Manager):
    def get_query_set(self):
        return super(BitsOfGoldPaymentMessagenManager, self)\
            .get_query_set().filter(source=settings.BITS_OF_GOLD_LABEL)