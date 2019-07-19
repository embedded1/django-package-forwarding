from django.db import models
from oscar.apps.payment.abstract_models import AbstractSource
from django.utils.translation import ugettext_lazy as _
from decimal import Decimal


class Source(AbstractSource):
    self_share = models.DecimalField(
        _("Self Share"), decimal_places=2, max_digits=12,
        default=Decimal('0.00'))
    partner_share = models.DecimalField(
        _("Partner Share"), decimal_places=2, max_digits=12,
        default=Decimal('0.00'))
    partner_paid = models.BooleanField(
        _("Partner got paid?"), default=False)

    def self_revenue(self):
        """
        This function returns our revenue.
        2 cases exist:
        1 - payment source includes our share
        2 - payment source doesn't include our share
        In both cases we check if postage was paid by partner, if it did we return the share
        otherwise we deduct the postage from our share
        """
        order = self.order
        self_share = self.self_share if self.self_share > 0 else order.total_incl_tax
        if order.partner_paid_for_shipping():
            #if self.partner_paid_shipping_insurance:
            #    return self_share
            return self.self_share - order.shipping_insurance_excl_tax
        return self_share - order.shipping_excl_tax - order.shipping_insurance_excl_tax

from oscar.apps.payment.models import *
