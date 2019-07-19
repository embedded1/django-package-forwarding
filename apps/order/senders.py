from django.db.models import get_model
from oscar.core.loading import get_class
from django.template import Context, loader
from post_office import mail
from django.conf import settings
import logging


logger = logging.getLogger("management_commands")
CommunicationEventType = get_model('customer', 'communicationeventtype')
Dispatcher = get_class('customer.utils', 'Dispatcher')


def send_order_confirmation_email_to_sitejabber(order):
    ctx = {
        'order_number': order.number,
        'customer_name': order.user.get_full_name(),
        'customer_email': order.user.email
    }
    # Load templates
    email_subject_tpl = loader.get_template('order/alerts/emails/sitejabber_order_confirmation_subject.txt')
    email_body_tpl = loader.get_template('order/alerts/emails/sitejabber_order_confirmation_body.txt')
    email_body_html_tpl = loader.get_template('order/alerts/emails/sitejabber_order_confirmation_body.html')

    ctx = Context(ctx)
    subject =  email_subject_tpl.render(ctx).strip()
    body = email_body_tpl.render(ctx)
    html_body = email_body_html_tpl.render(ctx)
    # Build email
    email = {
        'recipients': ['5534a7b34ec96@orders.sitejabber.com'],
        'sender': settings.OSCAR_FROM_EMAIL,
        'subject': subject,
        'message': body,
        'html_message': html_body
    }
    mail.send(**email)
