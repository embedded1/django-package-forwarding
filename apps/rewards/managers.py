from django.db import models

class AvailableCreditManager(models.Manager):
    def get_query_set(self):
        """
        Return ``QuerySet`` with product_class content pre-loaded.
        """
        return super(AvailableCreditManager, self).get_query_set()\
           .filter(date_redeemed__isnull=True, is_active=True)
