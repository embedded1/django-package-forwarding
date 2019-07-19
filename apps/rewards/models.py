from django.db import models
from django.utils.translation import ugettext_lazy as _
from .abstract_models import Reward


class LoyaltyReward(Reward):
    ORDER_FEEDBACK, PACKAGE_WEIGHT_BELOW_5_LBS,\
    PACKAGE_WEIGHT_EQUAL_OR_ABOVE_5_LBS = (
        'ORDER_FEEDBACK',
        'PACKAGE_WEIGHT_BELOW_5_LBS',
        'PACKAGE_WEIGHT_EQUAL_OR_ABOVE_5_LBS'
    )
    Loyalty_REWARD_TYPES = (
        (ORDER_FEEDBACK, 'Received order feedback'),
        (PACKAGE_WEIGHT_BELOW_5_LBS, 'Delivered package that weights < 5 lbs'),
        (PACKAGE_WEIGHT_EQUAL_OR_ABOVE_5_LBS, 'Delivered package that weights >= 5 lbs'),
    )
    type = models.CharField(max_length=64, choices=Loyalty_REWARD_TYPES)

    def __unicode__(self):
        return u"Loyalty reward of %s for %s" % (self.profile.user, self.type)

class ReferralReward(Reward):
    PACKAGE_DELIVERY, USER_SIGNUP = 'PACKAGE_DELIVERY', 'USER_SIGNUP'
    REFERRAL_REWARD_TYPES = (
        (PACKAGE_DELIVERY, 'Referee delivered a package'),
        (USER_SIGNUP, 'User signed up following a referral link'),
    )
    type = models.CharField(max_length=64, choices=REFERRAL_REWARD_TYPES)
    order = models.ForeignKey('order.Order', null=True, blank=True)

    def __unicode__(self):
        return u"Referral reward of %s for %s" % (self.profile.user, self.type)


class AffiliateReward(Reward):
    PAID_USER = 'PAID_USER'
    AFFILIATE_REWARD_TYPES = (
        (PAID_USER, 'Referred paid user'),
    )
    type = models.CharField(max_length=64, choices=AFFILIATE_REWARD_TYPES)
    order = models.ForeignKey('order.Order', null=True,
                              blank=True, related_name='affiliate_rewards')
    def __unicode__(self):
        return u"Affiliate reward of %s for %s" % (self.profile.user, self.type)


class CreditBenefit(models.Model):
    description = models.CharField(
        max_length=64, verbose_name=_("Benefit description"))

