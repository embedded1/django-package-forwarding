from django.core.management.base import BaseCommand
from apps.order.models import Order
from apps.order.models import ShippingLabelBatch
from django.core.exceptions import ObjectDoesNotExist
from decimal import Decimal as D
from optparse import make_option
import easypost as coreeasypost
from apps.shipping.apis import EasyPostAPI


class Command(BaseCommand):
    help = 'Purchase shipping label manually from previous order'
    option_list = BaseCommand.option_list + (
        make_option('-o', '--order_number', type='str',
            help="Order number to take common data from"),
         make_option('-c', '--carrier', type='str',
                    help="Shipping carrier name"),
         make_option('-s', '--service', type='str',
                    help="Shipping service name"),
    )

    def handle(self, verbosity, order_number, carrier, service, **options):
        easypost = EasyPostAPI()

        try:
            order = Order.objects\
                .select_related('package', 'user',
                                'package__customs_form')\
                .prefetch_related('package__stockrecords',
                                  'package__stockrecords__partner')\
                .get(number=order_number)
        except Order.DoesNotExist:
            print "order can't be found"
            return

        try:
            customs_form = order.package.customs_form
        except ObjectDoesNotExist:
                print "no customs form found"
                return

        shipment_kwargs = {
            'package_upc': order.package.upc,
            'shipping_addr': order.shipping_address,
            'weight': D(order.package.weight),
            'length': D(order.package.length),
            'width': D(order.package.width),
            'height': D(order.package.height),
            'carrier': carrier,
            'service': service,
            'customs_form': customs_form,
            'customer_name': order.user.get_full_name(),
            'customer_uuid': order.user.get_profile().uuid,
            'email': order.user.email,
            'partner': order.package.partner,
            'itn_number': None
        }

        shipment = easypost.create_shipment(**shipment_kwargs)
        if shipment is None:
            print "Shipment create failed"
            return

        try:
            batch = easypost.create_batch_and_buy(shipments=[shipment])
        except coreeasypost.Error as e:
            print "EasyPost create_batch_and_buy failed: %s" % e.message
            if e.param:
                print 'Specifically an invalid param: %s' % e.param
        else:
            #add the batch id to db for the cronjob to pick it up
            ShippingLabelBatch.objects\
                .create(batch_id=batch.id, partner=order.package.partner)
            #change package status, this removes the package from user's account
            order.package.status = 'postage_purchased'
            order.package.save()
            print "Shipping label batch created successfully"
            print shipment
