from datetime import datetime, timedelta
from django.template import Context, loader
from django.db.models import get_model
from oscar.core.loading import get_class
from django.db.models import Count
from django.core.management.base import BaseCommand
from django.utils import simplejson as json
from post_office import mail
from django.core.urlresolvers import reverse
from django.db.models import Q
from apps import utils
from django.conf import settings
from django.core.exceptions import ValidationError
from apps.order import senders
import logging


Order = get_model('order', 'Order')
Dispatcher = get_class('customer.utils', 'Dispatcher')
logger = logging.getLogger("management_commands")

def apply_order_filters(orders, enforce_min_order_num=False):
    """
    make sure we only 1 email to user as we may have the same user for multiple orders
    """
    current_user_id = None
    filtered_orders = []
    for order in orders:
        # if user doesn't have at least 2 orders we skip him
        if enforce_min_order_num and getattr(order, 'total_num_orders', 0) < 2:
            continue
        if current_user_id is None or current_user_id != order.user_id:
            filtered_orders.append(order)
        current_user_id = order.user_id
    return filtered_orders

class Command(BaseCommand):
    help = 'Send feedback requests to customers who placed an order recently'

    def handle(self, verbosity, **options):
        """
        This function does several things:
        1 - echos order to sitejabber for public review (most important), we select delivered orders
         or orders that were shipped 35 days ago
        2 - then, we pick all orders that we've echoed to SJ 3 days ago and we ask for friend invites
        3 - then, we pick all orders that we've echoed to SJ 5 days ago and we ask for order feedback on our site
        """

        #First we exclude all orders that feedback request was sent for them
        #then we get all orders in Delivered status or orders in Shipped status that were placed
        #30 days ago (we assume that 30 days is a reasonable time to receive the order for most cases)
        #The delivered status is not available for all packages therefore we need to have a workaround in place
        now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        #start_date = now - timedelta(days=35)
        #end_date = start_date + timedelta(hours=23, minutes=59, seconds=59)

        #exclude inactive users or sent requests
        potential_orders = Order.objects\
            .select_related('user')\
            .exclude(Q(feedback_request_sent=True) |
                     Q(user__is_active=False) |
                     Q(user__profile__account_status__verification_status="Failed") |
                     Q(user__id__in=settings.SITEJABBER_EXCLUDED_USERS) |
                     Q(status__in=['Cancelled', 'Pending', 'Refunded']))

        delivered_orders_qs = potential_orders\
            .annotate(total_num_orders=Count('user__orders', distinct=True))\
            .filter(status='Delivered')\
            .order_by('user__id')
        #assumed_delivered_orders_qs = potential_orders\
        #    .filter(status='Shipped', date_placed__range=(start_date, end_date))

        delivered_orders = list(delivered_orders_qs)
        #assumed_delivered_orders = list(assumed_delivered_orders_qs)
        orders = apply_order_filters(delivered_orders, enforce_min_order_num=True) #delivered_orders + assumed_delivered_orders

        # Load templates
        email_subject_tpl = loader.get_template('customer/alerts/emails/order_feedback_facebook_subject.txt')
        email_body_tpl = loader.get_template('customer/alerts/emails/order_feedback_facebook_body.txt')
        email_body_html_tpl = loader.get_template('customer/alerts/emails/order_feedback_facebook_body.html')

        #echo orders to sitejabber for public order feedback
        #senders.send_order_confirmation_email_to_sitejabber(order)

        emails = []
        for order in orders:
            #send this email only for customers
            data = {'full_name': order.user.get_full_name()}
            data.update(utils.get_site_properties())
            ctx = Context(data)
            subject =  email_subject_tpl.render(ctx).strip()
            body = email_body_tpl.render(ctx)
            html_body = email_body_html_tpl.render(ctx)

            # Build email and add to list
            email = {
                'recipients': [order.user.email],
                'sender': settings.OSCAR_FROM_EMAIL,
                'subject': subject,
                'message': body,
                'html_message': html_body
            }
            #add category for sendgrid analytics
            if not settings.DEBUG:
                email['headers'] = {'X-SMTPAPI': json.dumps({"category": "Order Feedback Facebook"})}
            # sending order feedback email is not disabled
            #emails.append(email)


        for email in emails:
            try:
                mail.send(**email)
            except ValidationError, e:
                logger.critical('Order feedback Facebook email send error: %s, email = %s'
                                % (str(e), email['recipients'][0]))

        feedback_sent_orders = Order.objects\
            .select_related('user')\
            .exclude(Q(feedback_request_sent=False) |
                     Q(user__is_active=False) |
                     Q(user__profile__account_status__verification_status="Failed") |
                     Q(user__id__in=settings.SITEJABBER_EXCLUDED_USERS))

        #send notifications about our referral program
        start_date = now - timedelta(days=3)
        end_date = start_date + timedelta(hours=23, minutes=59, seconds=59)
        feedback_sent_orders_3_days_ago = feedback_sent_orders\
            .filter(date_feedback_request_sent__range=(start_date, end_date))

        # Load templates
        email_subject_tpl = loader.get_template('customer/alerts/emails/referral_program_notification_subject.txt')
        email_body_tpl = loader.get_template('customer/alerts/emails/referral_program_notification_body.txt')
        email_body_html_tpl = loader.get_template('customer/alerts/emails/referral_program_notification_body.html')

        emails = []
        orders = apply_order_filters(feedback_sent_orders_3_days_ago)
        for order in orders:
            #send this email only for customers
            data = {
                'full_name': order.user.get_full_name()
            }
            data.update(utils.get_site_properties())
            ctx = Context(data)
            subject =  email_subject_tpl.render(ctx).strip()
            body = email_body_tpl.render(ctx)
            html_body = email_body_html_tpl.render(ctx)

            # Build email and add to list
            email = {
                'recipients': [order.user.email],
                'sender': settings.OSCAR_FROM_EMAIL,
                'subject': subject,
                'message': body,
                'html_message': html_body
            }
            #add category for sendgrid analytics
            if not settings.DEBUG:
                email['headers'] = {'X-SMTPAPI': json.dumps({"category": "Referral Program Notification"})}
            emails.append(email)

        for email in emails:
            try:
                mail.send(**email)
            except ValidationError, e:
                logger.critical('Referral Program notification email send error: %s, email = %s'
                                % (str(e), email['recipients'][0]))

        #now go over all orders that we've sent a feedback request 3 days ago
        #and ask for order feedback for our internal usage
        start_date = now - timedelta(days=5)
        end_date = start_date + timedelta(hours=23, minutes=59, seconds=59)
        feedback_sent_orders_5_days_ago = feedback_sent_orders\
            .filter(date_feedback_request_sent__range=(start_date, end_date))

        # Load templates
        email_subject_tpl = loader.get_template('customer/alerts/emails/order_feedback_subject.txt')
        #email_body_tpl = loader.get_template('customer/alerts/emails/order_feedback_body.txt')
        email_body_html_tpl = loader.get_template('customer/alerts/emails/order_feedback_body.html')

        #emails = []
        orders = apply_order_filters(feedback_sent_orders_5_days_ago)
        for order in orders:
            data = {
                'order': order,
                'full_name': order.user.get_full_name(),
                'survey_url': reverse('customer:feedback', kwargs={'pk': order.pk}),
                'contact_url': reverse('contact'),
                'order_delivered': True if order.status == 'Delivered' else False
            }
            data.update(utils.get_site_properties())
            ctx = Context(data)
            subject =  email_subject_tpl.render(ctx).strip()
            #body = email_body_tpl.render(ctx)
            #html_body = email_body_html_tpl.render(ctx)

            # Build email and add to list
        #    email = {
        #        'recipients': [order.user.email],
        #        'sender': settings.OSCAR_FROM_EMAIL,
        #        'subject': subject,
        #        'message': body,
        #        'html_message': html_body
        #    }
        #    #add category for sendgrid analytics
        #    if not settings.DEBUG:
        #        email['headers'] = {'X-SMTPAPI': json.dumps({"category": "Order Feedback"})}
        #    emails.append(email)

            data['no_display'] = True
            ctx = Context(data)
            html_body = email_body_html_tpl.render(ctx)
            #add site notification
            Dispatcher().notify_user(order.user, subject, html_body, category="Action")

        #we use celery to dispatch emails, therefore we iterate over all emails and add
        #each one of them to the task queue,send_many doesn't work with priority = now
        #therefore, we use the regular send mail
        #for email, order in zip(emails, feedback_sent_orders_5_days_ago):
        #    try:
        #        mail.send(**email)
        #    except ValidationError, e:
        #        logger.critical('order: #%s. feedback request email send error: %s, email = %s'
        #                        % (order.number, str(e), email['recipients'][0]))

        #update orders, we're doing bulk update and not to go through the order post_save signal
        #handler which will re send the shipped email
        #We're doing the update here not to include the orders that we've jest sent to SJ above
        #| assumed_delivered_orders_qs
        delivered_orders_qs.update(
            feedback_request_sent=True,
            date_feedback_request_sent=datetime.now())