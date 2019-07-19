from django.utils.translation import ugettext as _
from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from django.db.models import Q
from datetime import datetime, timedelta
from django.conf import settings
from django.template import Context, loader
from django.db.models import get_model, Min
from oscar.core.loading import get_class
from post_office import mail
from apps import utils
import logging


Product = get_model('catalogue', 'Product')
User = get_model('auth', 'User')
Dispatcher = get_class('customer.utils', 'Dispatcher')
logger = logging.getLogger("management_commands")

class Command(BaseCommand):
    """
    Check for packages with 3 days before storage fee applied and alert the user
    have registered for an alert.
    """
    help = _("Check for packages with 3 days before storage fee applied "
             "and send out alerts to customers")
    out_of_storage_statuses = ['paid', 'postage_mismatch', 'postage_purchased', 'shipped']

    def handle(self, **options):
        """
        Check all packages that have 3 days left to free storage and alert the customer
        Regular packages have 10 free days and consolidated packages have 30 free days
        therefore we separate both cases
        There's another interesting case which is packages that wait for consolidation - we can pick
        the oldest package in warehouse amount them and count it as consolidated package - the email notification
        will be changed though
        """
        emails = []
        alert_free_storage_days_left = getattr(settings, 'ALERT_FREE_STORAGE_DAYS_LEFT', 3)
        alert_package_consolidation_delivery_days_left = getattr(
            settings, 'ALERT_PACKAGE_CONSOLIDATION_DELIVERY_DAYS_LEFT', 3)
        consolidated_max_allowed_days = getattr(settings, 'CONSOLIDATED_FREE_STORAGE_IN_DAYS', 30)
        max_allowed_days = getattr(settings, 'FREE_STORAGE_IN_DAYS', 10)

        #get all in storage packages (exclude packages of inactive users and packages waiting for payment clearance)
        in_storage_pending_packages = Product.objects\
            .select_related('owner')\
            .exclude(Q(owner__is_active=False) | Q(status='pending_clearance'))\
            .filter(status__startswith='pending')

        now = datetime.now()
        #get only year month and day
        now = now.replace(hour=0, minute=0, second=0, microsecond=0)

        #start time of regular packages
        start_date = now - timedelta(days=max_allowed_days)
        #get end of day relative to start time, include the day as well
        end_date = start_date + timedelta(days=alert_free_storage_days_left, hours=23, minutes=59, seconds=59)

        #fetch all non consolidated packages currently in storage with 3 days or below left
        single_packages = list(in_storage_pending_packages.exclude(
            combined_products__isnull=False).filter(
            date_created__range=(start_date, end_date)))

        #start time of consolidated packages
        start_date = now - timedelta(days=consolidated_max_allowed_days)
        #get end of day relative to start time, include the day as well
        end_date =  start_date + timedelta(days=alert_free_storage_days_left, hours=23, minutes=59, seconds=59)

        #fetch all consolidated packages currently in storage with 3 days or below left
        consolidated_packages = list(in_storage_pending_packages.exclude(
            combined_products__isnull=True).filter(
            date_created__range=(start_date, end_date)))

        #fetch all recently consolidated packages - up to 3 days ago
        start_date = now - timedelta(days=alert_package_consolidation_delivery_days_left)
        end_date = now + timedelta(hours=23, minutes=59, seconds=59)
        recently_consolidated_packages = list(in_storage_pending_packages\
            .filter(date_consolidated__range=(start_date, end_date)))

        #fetch all users that have a package waiting for consolidation that about to expire
        start_date = now - timedelta(days=consolidated_max_allowed_days)
        #get end of day relative to start time, include the day as well
        end_date =  start_date + timedelta(days=alert_free_storage_days_left, hours=23, minutes=59, seconds=59)
        #old_consolidated_packages = list(in_storage_pending_packages\
        #    .filter(date_consolidated__range=(start_date, end_date)))

        users_with_waiting_for_consolidation_packages = list(Product.objects \
            .exclude(owner__is_active=False) \
            .filter(status__in=['waiting_for_consolidation',
                                'predefined_waiting_for_consolidation']) \
            .values('owner').annotate(oldest_package=Min('date_created')) \
            .filter(oldest_package__range=(start_date, end_date)))

        #fetch all packages that are in store for 30 days
        start_date = now - timedelta(days=30)
        end_date = start_date + timedelta(hours=23, minutes=59, seconds=59)
        packages_30_days_in_warehouse = list(Product.in_store_packages\
            .filter(owner__is_active=True, date_created__range=(start_date, end_date)))
        #fetch all packages that are in store for 60 days
        start_date = now - timedelta(days=60)
        end_date = start_date + timedelta(hours=23, minutes=59, seconds=59)
        packages_60_days_in_warehouse = list(Product.in_store_packages\
            .filter(owner__is_active=True, date_created__range=(start_date, end_date)))
        #fetch all packages that are in store for 90 days
        start_date = now - timedelta(days=90)
        end_date = start_date + timedelta(hours=23, minutes=59, seconds=59)
        packages_90_days_in_warehouse = list(Product.in_store_packages\
            .filter(owner__is_active=True, date_created__range=(start_date, end_date)))
        logger.info("Found %d regular packages with 3 days left to free storage",
                    len(single_packages))
        logger.info("Found %d consolidated packages with 3 days left to free storage",
                    len(consolidated_packages))
        logger.info("Found %d users with packages waiting for consolidation with 3 days left to free storage",
                    len(users_with_waiting_for_consolidation_packages))
        logger.info("Found %d packages that are in store for 30 days",
                    len(packages_30_days_in_warehouse))
        logger.info("Found %d packages that are in store for 60 days",
                    len(packages_60_days_in_warehouse))
        logger.info("Found %d packages that are in store for 90 days",
                    len(packages_90_days_in_warehouse))
        logger.info("Found %d consolidated packages with 3 days left for delivery",
                    len(recently_consolidated_packages))
        #logger.info("Found %d consolidated packages that wait 5 days for delivery",
        #            len(old_consolidated_packages))

        # Load templates
        email_subject_tpl = loader.get_template('customer/alerts/emails/free_storage_about_to_expire_subject.txt')
        email_body_tpl = loader.get_template('customer/alerts/emails/free_storage_about_to_expire_body.txt')
        email_body_html_tpl = loader.get_template('customer/alerts/emails/free_storage_about_to_expire_body.html')

        combined_packages = single_packages + consolidated_packages
        for package in combined_packages:
            data = {
                'package': package,
                'days_left': package.number_of_free_storage_days_left()
            }
            data.update(utils.get_site_properties())
            ctx = Context(data)
            subject =  email_subject_tpl.render(ctx).strip()
            body = email_body_tpl.render(ctx)
            html_body = email_body_html_tpl.render(ctx)

            # Build email and add to list
            email = {
                'recipients': [package.owner.email],
                'sender': settings.OSCAR_FROM_EMAIL,
                'subject': subject,
                'message': body,
                'html_message': html_body
            }
            emails.append(email)

            #add site notification
            data['no_display'] = True
            ctx = Context(data)
            html_body = email_body_html_tpl.render(ctx)
            Dispatcher().notify_user(package.owner, subject, html_body, category="Action")

        # Load templates
        email_subject_tpl = loader.get_template('customer/alerts/emails/waiting_for_consolidation_free_storage_about_to_expire_subject.txt')
        email_body_tpl = loader.get_template('customer/alerts/emails/waiting_for_consolidation_free_storage_about_to_expire_body.txt')
        email_body_html_tpl = loader.get_template('customer/alerts/emails/waiting_for_consolidation_free_storage_about_to_expire_body.html')

        for res in users_with_waiting_for_consolidation_packages:
            #need to get user object from user_id
            #we could write raw sql but this is not needed as this script runs once per day
            user = User.objects.get(pk=res['owner'])
            data = utils.get_site_properties()
            ctx = Context(data)
            subject =  email_subject_tpl.render(ctx).strip()
            body = email_body_tpl.render(ctx)
            html_body = email_body_html_tpl.render(ctx)

            # Build email and add to list
            email = {
                'recipients': [user.email],
                'sender': settings.OSCAR_FROM_EMAIL,
                'subject': subject,
                'message': body,
                'html_message': html_body
            }
            emails.append(email)

            data['no_display'] = True
            ctx = Context(data)
            html_body = email_body_html_tpl.render(ctx)
            #add site notification
            Dispatcher().notify_user(user, subject, html_body, category="Action")

        # Load templates
        email_subject_tpl = loader.get_template('customer/alerts/emails/long_storage_subject.txt')
        email_body_tpl = loader.get_template('customer/alerts/emails/long_storage_body.txt')
        email_body_html_tpl = loader.get_template('customer/alerts/emails/long_storage_body.html')
        packages_stored_for_long_time = packages_30_days_in_warehouse + \
                                        packages_60_days_in_warehouse + \
                                        packages_90_days_in_warehouse
        for package in packages_stored_for_long_time:
            data = {
                'package': package,
                'storage_days': package.get_storage_days()
            }
            data.update(utils.get_site_properties())
            ctx = Context(data)
            subject =  email_subject_tpl.render(ctx).strip()
            body = email_body_tpl.render(ctx)
            html_body = email_body_html_tpl.render(ctx)

            # Build email and add to list
            email = {
                'recipients': [package.owner.email],
                'sender': settings.OSCAR_FROM_EMAIL,
                'subject': subject,
                'message': body,
                'html_message': html_body
            }
            emails.append(email)

            #add site notification
            data['no_display'] = True
            ctx = Context(data)
            html_body = email_body_html_tpl.render(ctx)
            Dispatcher().notify_user(package.owner, subject, html_body, category="Action")

        # Load templates
        email_subject_tpl = loader.get_template('customer/alerts/emails/post_consolidation_notice_subject.txt')
        email_body_tpl = loader.get_template('customer/alerts/emails/post_consolidation_notice_body.txt')
        email_body_html_tpl = loader.get_template('customer/alerts/emails/post_consolidation_notice_body.html')
        for package in recently_consolidated_packages:
            data = {
                'package': package,
                'days_left': package.number_of_post_consolidation_delivery_days()
            }
            data.update(utils.get_site_properties())
            ctx = Context(data)
            subject =  email_subject_tpl.render(ctx).strip()
            body = email_body_tpl.render(ctx)
            html_body = email_body_html_tpl.render(ctx)

            # Build email and add to list
            email = {
                'recipients': [package.owner.email],
                'sender': settings.OSCAR_FROM_EMAIL,
                'subject': subject,
                'message': body,
                'html_message': html_body
            }
            emails.append(email)

            #add site notification
            data['no_display'] = True
            ctx = Context(data)
            html_body = email_body_html_tpl.render(ctx)
            Dispatcher().notify_user(package.owner, subject, html_body, category="Action")

        # Load templates
        #email_subject_tpl = loader.get_template('customer/alerts/emails/cancel_consolidation_notice_subject.txt')
        #email_body_tpl = loader.get_template('customer/alerts/emails/cancel_consolidation_notice_body.txt')
        #email_body_html_tpl = loader.get_template('customer/alerts/emails/cancel_consolidation_notice_body.html')
        #for package in old_consolidated_packages:
        #    data = {'package': package}
        #    data.update(utils.get_site_properties())
        #    ctx = Context(data)
        #    subject =  email_subject_tpl.render(ctx).strip()
        #    body = email_body_tpl.render(ctx)
        #    html_body = email_body_html_tpl.render(ctx)

        #    # Build email and add to list
        #    email = {
        #        'recipients': [package.owner.email],
        #        'sender': settings.OSCAR_FROM_EMAIL,
        #        'subject': subject,
        #        'message': body,
        #        'html_message': html_body
        #    }
        #    emails.append(email)

        #    #add site notification
        #    data['no_display'] = True
        #    ctx = Context(data)
        #    html_body = email_body_html_tpl.render(ctx)
        #    Dispatcher().notify_user(package.owner, subject, html_body, category="Action")

        #we use celery to dispatch emails, therefore we iterate over all emails and add
        #each one of them to the task queue,send_many doesn't work with priority = now
        #therefore, we use the regular send mail
        for email in emails:
            try:
                mail.send(**email)
            except ValidationError, e:
                logger.critical('send_storage_alerts post_office send validation error: %s, email = %s'
                                % (str(e), email['recipients'][0]))


