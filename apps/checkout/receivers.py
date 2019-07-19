from oscar.apps.checkout.signals import post_checkout
from django.core.exceptions import ObjectDoesNotExist
from django.dispatch import receiver
from django.conf import settings
from decimal import Decimal as D
from apps.rewards.models import ReferralReward
from apps.order.models import OrderTracking, ShippingLabel
from apps.rewards import responses
from ipware.ip import get_real_ip
from pinax.referrals.models import ReferralResponse
from . import cache
import logging

logger = logging.getLogger("management_commands")

def reward_package_delivery(user):
    """
    package delivery reward is given only for the first delivery and
    only if the user who delivered the package signed up through a referral link
    This function returns True if and only if both conditions apply
    """
    try:
        ReferralResponse.objects \
            .get(user=user, action="USER_SIGNUP")
    except:
        return False

    return user.orders.all().count() == 1

def redeem_referral_credit(order):
    """
    This function supports cases where partial credit is used
    In such cases we create new reward with the left unused credit
    """
    redeemed_credit = D('0.00')
    applied_referral_credit = order.get_applied_referral_credit()
    if applied_referral_credit > 0:
        rewards = ReferralReward.available_credit\
            .filter(profile=order.user.get_profile())\
            .order_by('-amount')

        for reward in rewards:
            cur_credit = reward.amount

            if redeemed_credit + cur_credit <= applied_referral_credit:
                redeemed_credit += cur_credit
                reward.date_redeemed=order.date_placed.date()
                reward.order = order
                reward.save()
            else:
                #calculate unused credit
                partial_used_credit = applied_referral_credit - redeemed_credit
                unused_credit = cur_credit - partial_used_credit
                #redeem the left credit
                reward.amount = partial_used_credit
                reward.date_redeemed=order.date_placed.date()
                reward.order = order
                reward.save()
                #create new reward with the unused credit
                ReferralReward.objects.create(
                    profile=reward.profile,
                    type=reward.type,
                    amount=unused_credit)
                redeemed_credit = applied_referral_credit

            if redeemed_credit == applied_referral_credit:
                break

def process_referral_credit(order):
    """
    Currently, this function does only one thing:
    we need to redeem referral credit if applied to basket
    """
    #first we redeem used credit
    redeem_referral_credit(order)


@receiver(post_checkout)
def post_checkout_callback(sender, order, user, request, response,
                           package, is_return_to_store, shipping_label_id, **kwargs):
    is_prepaid_return_label = is_return_to_store and \
                              order.shipping_code == 'no-shipping-required'

    #Link package to order
    order.package = package

    #save order related data
    shipping_insurance_upc = settings.SHIPPING_INSURANCE_TEMPLATE % package.upc
    try:
        shipping_insurance = package.variants.get(upc=shipping_insurance_upc)
    except ObjectDoesNotExist:
        pass
    else:
        order.shipping_insurance = True
        order.shipping_insurance_incl_tax = shipping_insurance.stockrecord.price_excl_tax
        order.shipping_insurance_excl_tax = shipping_insurance.stockrecord.cost_price

    #We finished updating the order, now its time to save it
    order.save()

    #give referrer credit for first package delivery (if needed)
    #we only give credit for the first package delivery if the user signed up through
    #referral link. therefore we create this reward only if this is the first order the user placed.
    if reward_package_delivery(user):
        responses.credit_package_delivery(request, order)

    #give credit for user based on delivered package weight
    #responses.credit_package_weight(user, weight=package.weight)
    #redeem referral credit - we do it to avoid gaming the system and getting multiple discounts
    #on the same credit
    process_referral_credit(order)

    #Create the order tracking object and link it to order
    #read carrier value from cache and store in db
    carrier_key = "%s_%s" % (package.upc, 'carrier')
    carrier = cache.get_order_tracking_value(carrier_key)
    display_carrier_key = "%s_%s" % (package.upc, 'display_carrier')
    display_carrier = cache.get_order_tracking_value(display_carrier_key)
    if not carrier:
        #prepaid return label, no shipping required
        if is_prepaid_return_label:
            display_carrier = carrier = 'N/A'
        #fallback to usps
        else:
            display_carrier = carrier = 'USPS'
            logger.critical("Carrier couldn't be fetched from cache on order completion, order id = %s" % order.id)


    OrderTracking.objects.create(
        order=order,
        carrier=carrier,
        display_carrier=display_carrier
    )

    #We need to link order to shipping label object in case we're dealing with
    #prepaid return to merchant checkout
    if is_prepaid_return_label and shipping_label_id:
        ShippingLabel.objects.filter(pk=shipping_label_id).update(order=order)

    #need to store maxmind related data in cache for later usage
    #once we receive the IPN message for that order
    ip = get_real_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT')
    accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE')
    cache.store_maxmind_data(key=order.number, val=(ip, user_agent, accept_language))
