from oscar.apps.offer import models
from decimal import Decimal as D
import datetime
#from oscar.apps.offer.custom import create_condition


class ReferralProgram(models.Condition):
    name = "User must have enough referral credit"
    description = "Discount off shipping for referral and referee"

    def __init__(self, *args, **kwargs):
        super(ReferralProgram, self).__init__(*args, **kwargs)
        self.value = D('5.0')

    class Meta:
        proxy = True

    def is_satisfied(self, offer, basket):
        """
        Returns True if the user has enough referral credit for this offer
        and the checkout process is not return-to-merchant
        """
        if basket.type == 'RETURN_TO_MERCHANT':
            return False
        if not basket.owner:
            return False
        profile = basket.owner.get_profile()
        if not profile:
            return False
        return profile.referral_unredeemed_credit() >= self.value

    def consume_items(self, offer, basket, affected_lines):
        """
        This offer runs first, we need to consume affected lines so no other
        discount will be applied.
        As we only give discount off shipping service, only 1 line should be affected
        """
        for line, __, quantity in affected_lines:
            line.consume(quantity)


class BlackFriday(models.Condition):
    name = "User must qualified for the Black Friday promotion"
    description = "Black friday discount"

    def is_satisfied(self, offer, basket):
        """
        Returns True if the user is qualified for this promotion
        and if the package received after a specific date which is in
        our case 11/27/2016
        """
        if basket.type == 'RETURN_TO_MERCHANT':
            return False
        if not basket.owner:
            return False
        profile = basket.owner.get_profile()
        if not profile:
            return False
        package = basket.package
        if not package:
            return False
        cutoff_date = datetime.datetime(2016, 11, 25, 0, 0, 0)
        return profile.qualified_for_black_friday_promo and\
               package.date_created > cutoff_date

    def consume_items(self, offer, basket, affected_lines):
        """
        This offer runs first, we need to consume affected lines so no other
        discount will be applied.
        As we only give discount off shipping service, only 1 line should be affected
        """
        for line, __, quantity in affected_lines:
            line.consume(quantity)

    class Meta:
        proxy = True

class PurseIOExclusiveClub(models.Condition):
    name = "User must qualified for Purse.io exclusive club promotion"
    description = "Exclusive club discount"

    def is_satisfied(self, offer, basket):
        """
        Returns True if the user is qualified for exclusive club promotion

        """
        if not basket.owner:
            return False
        profile = basket.owner.get_profile()
        if not profile:
            return False
        #verify that user was coming from Purse.io
        return profile.is_qualified_for_exclusive_club_offers('purse')

    def consume_items(self, offer, basket, affected_lines):
        """
        This offer runs first, we need to consume affected lines so no other
        discount will be applied.
        As we only give discount off shipping service, only 1 line should be affected
        """
        for line, __, quantity in affected_lines:
            line.consume(quantity)

    class Meta:
        proxy = True

#create_condition(ReferralProgram)