from django.db.models.signals import post_save
from apps.order.signals import order_confirmed
from apps.rewards.models import ReferralReward
from django.db.models import get_model
from django.dispatch import receiver
from pinax.referrals.models import ReferralResponse
from apps.customer.tasks import mixpanel_track_completed_order, ga_track_completed_order, subscribe_user
from oscar.core.loading import get_class
from .models import Order
from django.conf import settings
import logging

logger = logging.getLogger("management_commands")
CommunicationEventType = get_model('customer', 'communicationeventtype')
Dispatcher = get_class('customer.utils', 'Dispatcher')

def process_package_delivery_credit(order):
    #We give credit to the referrer for package delivery (not including return to store delivery)
    #here as at this stage the order was completed successfully and
    #has shipping label which means we're ready to mail it out after it passed all validations.
    #we look for a previous inactive reward that was created upon order
    if not order.is_prepaid_return_to_store() and \
       not order.is_return_to_store():
        package_delivery_reward = ReferralReward.objects\
            .filter(order__user=order.user,
                    type=ReferralReward.PACKAGE_DELIVERY,
                    is_active=False)
        if package_delivery_reward.exists():
            package_delivery_reward.update(is_active=True, order=order)
            #notify referrer that he just receives the package delivery credit
            try:
                response = ReferralResponse.objects\
                    .get(user=order.user,
                         action=ReferralReward.PACKAGE_DELIVERY)
            except ReferralResponse.DoesNotExist:
                logger.critical("No PACKAGE_DELIVERY response found when trying to give such credit")
            else:
                referral = response.referral.user
                ctx = {
                    'referee_name': order.user.get_full_name,
                    'is_affiliate': response.referral.user.get_profile().is_affiliate_account()
                }
                msgs = CommunicationEventType.objects.get_and_render(
                        code='PACKAGE_DELIVERY_REWARD', context=ctx)
                dispatcher = Dispatcher()
                dispatcher.dispatch_user_messages(referral, msgs)
                #add site notification
                ctx['no_display'] = True
                msgs = CommunicationEventType.objects.get_and_render(
                        code='PACKAGE_DELIVERY_REWARD', context=ctx)
                dispatcher.notify_user(referral, msgs['subject'], msgs['html'], category='Info')


@receiver(post_save, sender=Order)
def order_post_save_handler(sender, instance, created, **kwargs):
    """
    Here we send out shipped order email only as it doesn't require any
    extra arguments or custom processing
    """
    order = instance

    if order.status == 'Shipped':
        ctx = {'order_number': order.number}
        logger.info("Sending email alert for shipped order: #%s" % order.number)
        if order.is_prepaid_return_to_store():
            communication_type_code = 'SHIPPED_PREPAID_RETURN_LABEL_ORDER'
        else:
            ctx.update({
                'carrier': order.tracking.carrier,
                'display_carrier': order.tracking.display_carrier,
                'shipping_method': order.shipping_method,
                'tracking_number': order.tracking.tracking_number
            })
            communication_type_code = 'SHIPPED_ORDER'
        msgs = CommunicationEventType.objects.get_and_render(
                code=communication_type_code, context=ctx)
        dispatcher = Dispatcher()
        dispatcher.dispatch_order_messages(order, msgs)
        #add site notification
        ctx['no_display'] = True
        msgs = CommunicationEventType.objects.get_and_render(
                code='SHIPPED_ORDER', context=ctx)
        dispatcher.notify_user(order.user, msgs['subject'], msgs['html'], category='Info')
    elif order.status == 'Processed':
        process_package_delivery_credit(order)
        #move orders with prepaid return label to Shipped status as
        #we don't get any notifications for such orders
        if order.is_prepaid_return_to_store():
            order.set_status('Shipped')
    #elif order.status == 'Cancelled':
    #order cancellation logic is placed in the cancel_order function


    #those are the statuses that means that the order passed all validations and
    #payment has been sent to partner (if required) and now we either wait for shipping label
    #or we provided with pre paid label, now its the perfect time to change status to settled
    #elif order.status in ['In process', 'Wait for return label download']:
    #    #order passed all validations we can now safely change fees status to settled
    #    package = order.package
    #    #set all fee objects and combined_products object status to settled
    #    package.variants.all().update(status="settled")
    #    all_combined_products = package.combined_products.all()
    #    all_combined_products.update(status="settled")
    #    for combined_product in all_combined_products:
    #        combined_product.variants.all().update(status="settled")

@receiver(order_confirmed)
def order_confirmed_handler(sender, order, **kwargs):
    from apps.user.alerts import send_order_complete_alert
    from apps.customer.alerts.senders import send_order_confirmation_email
    #Send order confirmation to user
    send_order_confirmation_email(order)
    #mail admins on every successful order
    send_order_complete_alert(order)
    #track completed order in Mixpanel and Google Analytics
    mixpanel_track_completed_order.apply_async(
        kwargs={'order_id': order.id},
        queue='analytics'
    )
    ga_track_completed_order.apply_async(
        kwargs={'order_id': order.id},
        queue='analytics'
    )
    #add user to the customers group
    list_id = settings.MAILCHIMP_LISTS[settings.MAILCHIMP_LIST_USERS]
    group_id = settings.MAILCHIMP_LIST_GROUPS[list_id][settings.MAILCHIMP_GROUP_CUSTOMERS]
    subscribe_user.apply_async(
        kwargs={
            'user': order.user,
            'list_id': list_id,
            'group_settings': {group_id: True}
        },
        queue='analytics')

