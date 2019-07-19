from __future__ import absolute_import
from packageshop.celery import app
from paypal.adaptive.facade import pay_secondary_receivers
from paypal import exceptions
import logging

logger = logging.getLogger("management_commands")


@app.task(ignore_result=True)
def pay_secondary_receiver(order):
    pay_key = order.get_pay_key()
    if pay_key:
        try:
            #transfer partner share
            pay_secondary_receivers(pay_key)
            #mark that partner was fully paid
            source = order.get_payment_source()
            source.partner_paid = True
            source.save()
        except exceptions.PayPalError:
            logger.critical("Transfer payment for secondary receiver failed!, pay_key = %s" % pay_key)
        finally:
            order.set_status('Processed')