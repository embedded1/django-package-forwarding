from django.core import mail
from django.template import loader, Context
import logging


logger = logging.getLogger("management_commands")


def send_new_user_alert(user):
    """
    Send an alert to admins on every new registered user
    """
    profile = user.get_profile()
    ctx = Context({
        'user': user,
        'followed_referral_link': profile.is_registered_through_referral_link(),
        'is_affiliate': profile.is_affiliate_account()
    })
    subject_tpl = loader.get_template('user/alerts/emails/admins/new_user_subject.txt')
    body_tpl = loader.get_template('user/alerts/emails/admins/new_user_body.txt')
    body_html_tpl = loader.get_template('user/alerts/emails/admins/new_user_body.html')
    mail.mail_admins(
        subject=subject_tpl.render(ctx).strip(),
        message=body_tpl.render(ctx),
        html_message=body_html_tpl.render(ctx)
    )


def send_new_package_alert(package):
    """
    Send an alert to admins on every successful order
    """
    ctx = Context({
        'package': package
    })
    subject_tpl = loader.get_template('user/alerts/emails/admins/new_package_subject.txt')
    body_tpl = loader.get_template('user/alerts/emails/admins/new_package_body.txt')
    body_html_tpl = loader.get_template('user/alerts/emails/admins/new_package_body.html')

    mail.mail_admins(
        subject=subject_tpl.render(ctx).strip(),
        message=body_tpl.render(ctx),
        html_message=body_html_tpl.render(ctx)
    )


def send_order_complete_alert(order):
    """
    Send an alert to admins on every successful order
    """
    ctx = Context({
        'order': order
    })
    subject_tpl = loader.get_template('user/alerts/emails/admins/successful_order_subject.txt')
    body_tpl = loader.get_template('user/alerts/emails/admins/successful_order_body.txt')
    body_html_tpl = loader.get_template('user/alerts/emails/admins/successful_order_body.html')

    mail.mail_admins(
        subject=subject_tpl.render(ctx).strip(),
        message=body_tpl.render(ctx),
        html_message=body_html_tpl.render(ctx)
    )

def send_fraud_order_alert(order, err_msg):
    """
    Send an alert to admins on every order that requires pending fraud validation
    """
    ctx = Context({
        'order': order,
        'risk_score': order.risk_score,
        'err_msg': err_msg
    })
    subject_tpl = loader.get_template('user/alerts/emails/admins/order_pending_fraud_check_subject.txt')
    body_tpl = loader.get_template('user/alerts/emails/admins/order_pending_fraud_check_body.txt')
    body_html_tpl = loader.get_template('user/alerts/emails/admins/order_pending_fraud_check_body.html')

    mail.mail_admins(
        subject=subject_tpl.render(ctx).strip(),
        message=body_tpl.render(ctx),
        html_message=body_html_tpl.render(ctx)
    )