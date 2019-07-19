from datetime import datetime
from django.db import models
from .managers import AvailableCreditManager

class Reward(models.Model):
    profile = models.ForeignKey('user.Profile', related_name="%(app_label)s_%(class)s_related")
    amount = models.DecimalField(max_digits=10, decimal_places=2, db_index=True)
    date_credited = models.DateTimeField(auto_now_add=True)
    date_redeemed = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)

    objects = models.Manager()
    available_credit = AvailableCreditManager()

    @property
    def redeemed(self):
        return self.date_redeemed is not None

    def redeem(self):
        self.date_redeemed = datetime.now()
        self.save()

    class Meta:
        abstract = True