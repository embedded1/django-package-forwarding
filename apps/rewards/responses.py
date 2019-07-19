from pinax.referrals.models import Referral
from apps.rewards.models import LoyaltyReward, ReferralReward
from django.conf import settings
import logging

logger = logging.getLogger("management_commands")


def record_referrer_response(request, action):
    """
    Here we give credit to the referrer
    """
    return Referral.record_response(request, action)

def give_referral_credit(user, action, order=None, is_active=True, is_affiliate=False):
    """
    We have a guard here against cases we're trying to give referral rewards
    by mistake, as our business model gives one referral reward per type and user
    we only create the reward only if it does not exist
    """
    profile = user.get_profile()
    try:
        if order:
            ReferralReward.objects.get(
                profile=profile,
                type=action,
                order__user=order.user)
        else:
            ReferralReward.objects.get(
                profile=profile,
                type=action)
    except ReferralReward.DoesNotExist:
        reward_amount = settings.REFERRAL_PROGRAM_CREDITS[action] if not is_affiliate else\
            settings.AFFILIATE_PROGRAM_CREDITS[action]
        ReferralReward.objects.create(
            profile=profile,
            amount=reward_amount,
            type=action,
            order=order,
            is_active=is_active)
    else:
        logger.critical("We're trying to give a referral reward by mistake."
                        " user = %s, action = %s" % (user, action))

def give_loyalty_credit(user, action):
    """
    Here we give credit to the user who took a specific action
    Currently all loyalty credit are only for audit
    We want to go live with simple design at first stage
    """
    LoyaltyReward.objects.create(
        profile=user.get_profile(),
        amount=settings.LOYALTY_PROGRAM_CREDITS[action],
        type=action,
        is_active=False)

def credit_signup(request):
    """
    We give credit to every user who signed up by following a referral link
    This does not apply for the affiliate program
    """
    response = record_referrer_response(request, ReferralReward.USER_SIGNUP)
    if response:
        is_affiliate = response.referral.user.get_profile().is_affiliate_account()
        if not is_affiliate:
            give_referral_credit(response.user, ReferralReward.USER_SIGNUP)
        else:
            # no need to send notification to the referral
            response = None
        return response
    return None


def credit_package_delivery(request, order):
    """
    We give credit to the referral when the referee has delivered
    a package.
    we set the initial state of the reward to inactive as we need to wait
    for order confirmation, it the order isn't confirmed we use the owner
    to identify this reward when confirmed order arrives.
    """
    response = record_referrer_response(request, ReferralReward.PACKAGE_DELIVERY)
    if response:
        is_affiliate = response.referral.user.get_profile().is_affiliate_account()
        give_referral_credit(response.referral.user,
                             ReferralReward.PACKAGE_DELIVERY,
                             is_active=False,
                             order=order,
                             is_affiliate=is_affiliate)
        return response
    return None

def credit_order_feedback(user):
    """
    We give credit to the user who gave feedback on his order
    """
    give_loyalty_credit(user, "ORDER_FEEDBACK")


def credit_package_weight(user, weight):
    """
    We give credit to users who delivered packages with us.
    We have 2 credit amounts based on package weight
    """
    if weight < 5:
        give_loyalty_credit(user, "PACKAGE_WEIGHT_BELOW_5_LBS")
    else:
        give_loyalty_credit(user, "PACKAGE_WEIGHT_EQUAL_OR_ABOVE_5_LBS")
