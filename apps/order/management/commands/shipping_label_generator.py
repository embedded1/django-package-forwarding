from django.utils.translation import ugettext as _
from django.core.management.base import BaseCommand
from django.db.models import get_model
from django.conf import settings
from apps.shipping.apis import EasyPostAPI
from operator import itemgetter
from django.core.files import File
from apps.shipping.utils import add_shipping_event
from django.core.files.temp import NamedTemporaryFile
import requests
import easypost as coreeasypost
from apps.order.tasks import pay_secondary_receiver
import logging
from decimal import Decimal as D


ShippingLabelBatch = get_model('order', 'ShippingLabelBatch')
ShippingLabel = get_model('order', 'ShippingLabel')
Order = get_model('order', 'Order')
ExpressCarrierCommercialInvoice = get_model('order', 'ExpressCarrierCommercialInvoice')
logger = logging.getLogger("management_commands")

MIN_INSURANCE_VALUE = D('100.0')

class Command(BaseCommand):
    """
    Purchase shipping labels for all recent cleared orders
    """
    help = _("Purchase shipping labels for successful orders")

    @staticmethod
    def download_file(label_url, suffix):
        r = requests.get(label_url)
        file_temp = NamedTemporaryFile(delete=True, suffix=suffix)
        file_temp.write(r.content)
        file_temp.flush()
        return File(file_temp)

    def download_shipping_label(self, label_url, order, file_name, suffix):
        if label_url:
            shipping_label = ShippingLabel(
                order=order,
                caption=file_name+suffix
            )
            #download shipping label in png format
            shipping_label_file = self.download_file(label_url, suffix)
            shipping_label.original.save(file_name+suffix, shipping_label_file, save=False)
            shipping_label.save()
            shipping_label_file.close()

    def download_shipping_labels(self, shipment, order):
        """
        TNT is special, we can only work with the PDF label, the converating to other
        format is not working properly
        """
        file_name = 'order_%s_shipping_label' % order.number
        if shipment.selected_rate.carrier == settings.EASYPOST_TNTEXPRESS:
            #only pdf label can be used
            pdf_label_url = shipment.postage_label.label_url
            self.download_shipping_label(pdf_label_url, order, file_name, '.pdf')
        else:
            #request the png and zpl formats, pdf was requested before
            shipment.label(file_format='pdf')
            shipment.label(file_format='zpl')
            pdf_label_url = shipment.postage_label.label_pdf_url
            zpl_label_url = shipment.postage_label.label_zpl_url
            png_label_url = shipment.postage_label.label_url
            self.download_shipping_label(png_label_url, order, file_name, '.png')
            self.download_shipping_label(zpl_label_url, order, file_name, '.zpl')
            self.download_shipping_label(pdf_label_url, order, file_name, '.pdf')

    def download_commercial_invoices(self, order, forms):
        downloaded_files = []
        commercial_invoice_objs = []
        for i, form in enumerate(forms):
            if form['form_type'] == 'commercial_invoice':
                commercial_invoice = ExpressCarrierCommercialInvoice(order=order)
                #download shipping label in png format
                invoice_file = self.download_file(form['form_url'], '.pdf')
                invoice_file_name = 'order_%s_commercial_invoice_%d.pdf' % (order.number if order else 'manual', i)
                commercial_invoice.original.save(invoice_file_name, invoice_file, save=False)
                downloaded_files.append(invoice_file)
                commercial_invoice_objs.append(commercial_invoice)

        #save all objects to DB at once
        if len(commercial_invoice_objs) > 0:
            ExpressCarrierCommercialInvoice.objects.bulk_create(commercial_invoice_objs)

        #Delete all temp files
        for downloaded_file in downloaded_files:
            downloaded_file.close()


    @staticmethod
    def collect_shipments_errors(shipments, batch_id):
        shipment_errors = []
        for shipment in shipments:
            try:
                batch_message = shipment['batch_message']
                if batch_message:
                    shipment_errors.append({shipment['id']: batch_message})
            except KeyError:
                pass
        if shipment_errors:
            logger.critical("batch: %s, shipments errors: %s", batch_id, shipment_errors)

    def refund_shipment(self, order, package, shipment, msg):
        #first get refund
        refund = shipment.refund()
        #save shipment_id and refund_id for audit
        order.tracking.shipment_id = shipment.id
        #order.tracking.tracking_number = refund.id
        order.tracking.save()
        package.status = 'postage_mismatch'
        package.save()
        order.set_status('Postage refunded')
        #add shipping event to mark items as refunded
        add_shipping_event(order, notes=msg, event_type_name='Refund')
        logger.critical("Postage refunded for package: #%s, don't mail it out!" % package.upc)

    def transfer_payment_to_partner(self, order):
        pay_secondary_receiver.apply_async(
            kwargs={'order': order},
            queue='payments')

    def handle(self, **options):
        easypost = EasyPostAPI()
        batches = ShippingLabelBatch.objects.prefetch_related('orders').filter(
            status__in=[ShippingLabelBatch.STATUS.queued, ShippingLabelBatch.STATUS.label_generating])
        for batch in batches:
            try:
                easypost_batch = easypost.retrieve_batch(batch.batch_id)
                if easypost_batch.state == 'created':
                    easypost_batch.buy()
                    easypost_batch.refresh()
                elif easypost_batch.state == 'creation_failed':
                    logger.critical("Creation of batch: %s has failed" % batch)
                    #collect shipments error messages
                    self.collect_shipments_errors(easypost_batch.shipments, batch.id)
                    batch.status = ShippingLabelBatch.STATUS.creation_failed
                    batch.save()
                    #change orders status so we could pick them up for generating new labels
                    batch.orders.all().update(status='In process')
                elif easypost_batch.state == 'purchase_failed':
                    logger.critical("Postage purchase of batch: %s has failed" % batch)
                    postage_errors = 0
                    #collect shipments error messages
                    self.collect_shipments_errors(easypost_batch.shipments, batch.id)
                    #change orders that failed the postage purchase to In Process so we could pick
                    #them up later
                    failed_shipments = []
                    failed_packages = []

                    for shipment in easypost_batch.shipments:
                        if shipment.batch_status != "postage_purchased":
                            postage_errors += 1
                            failed_shipments.append({'id': shipment.id})
                            failed_packages.append(shipment.reference)

                    if failed_packages:
                        batch.orders.filter(package__upc__in=failed_packages).update(status='In process')

                    #we set batch status based on the number of failed postage purchases
                    if postage_errors == len(easypost_batch.shipments):
                        batch.status = ShippingLabelBatch.STATUS.purchase_failed
                        batch.save()
                    else:
                        # we got some shipments that contain label, need to remove failed shipments and
                        # continue generating label
                        easypost_batch.remove_shipments(shipments=failed_shipments)
                elif easypost_batch.state == 'purchased':
                    #generate label
                    easypost_batch.label(file_format='zpl')
                #sometimes, batches stuck in label_generation status even though the labels
                #were already generated
                elif (easypost_batch.state == 'label_generated') or \
                     (easypost_batch.state == 'label_generating' and easypost_batch.label_url):
                    #build the shipments list
                    sorted_shipments = []
                    postage_errors = 0
                    for shipment in easypost_batch.shipments:
                        sorted_shipments.append(easypost.retrieve_shipment(shipment.id))
                    #sort the list by package.upc which is stored in reference
                    sorted_shipments.sort(key=itemgetter('reference'))
                    orders = list(batch.orders.select_related(
                        'tracking', 'package', 'user').all().order_by('package__upc'))

                    #special handling for manually purchased labels, where no order exists
                    if not orders:
                        orders = [None]

                    #change batch status to generated before we start the processing
                    #to eliminate cases where the cron job is re-triggered and the previous
                    #processing is still in progress
                    #batch.status = ShippingLabelBatch.STATUS.label_generated
                    #batch.save()

                    #go over each shipment and do some work
                    for s, order in zip(sorted_shipments, orders):
                        #postage was purchased
                        if order:
                            if s.batch_status == "postage_purchased":
                                postage_error = False
                                shipment = easypost.retrieve_shipment(s.id)
                                package = order.package
                                tracking_number = shipment.tracking_code
                                insurance_needed = order.shipping_insurance
                                if insurance_needed:
                                    amount = order.package.total_content_value()
                                    #minimum content value eligible for insurance is $100
                                    if amount < MIN_INSURANCE_VALUE:
                                        amount = MIN_INSURANCE_VALUE
                                    try:
                                        ins_amount = easypost.create_insurance(
                                            shipment=shipment,
                                            amount=amount
                                        )
                                    except coreeasypost.Error as e:
                                        if "The shipment is already insured" not in e.message:
                                            raise e
                                    else:
                                        if D(ins_amount) != amount:
                                            logger.critical("EasyPost - insurance of package %s failed, order #%s, shipment #%s"
                                                            % (package.upc, order.number, shipment.id))
                                            postage_error = True
                                #verify selected rate matches the shipping method selected by the customer
                                selected_rate = s.selected_rate
                                easypost_msg = ""
                                if not selected_rate:
                                    postage_error = True
                                    easypost_msg = "EasyPost - no selected rate, order carrier = %s," \
                                                   " shipment id = %s" % (order.tracking.carrier, s.id)
                                    logger.critical(easypost_msg)
                                else:
                                    if selected_rate.carrier.lower() != order.tracking.carrier.lower():
                                        postage_error = True
                                        easypost_msg = "EasyPost - carriers don't match, order carrier = %s," \
                                                       " shipment carrier = %s" % (order.tracking.carrier, selected_rate.carrier)
                                        logger.critical(easypost_msg)

                                    order_service = order.shipping_code.split('-')[0]
                                    if selected_rate.service.lower() != order_service.lower():
                                        postage_error = True
                                        easypost_msg = "EasyPost - services don't match, order service = %s," \
                                                       " shipment service = %s" % (order_service, selected_rate.service)
                                        logger.critical(easypost_msg)

                                    #dirty patch for Danill's and Denis's orders that somehow show different rates at purchase
                                    if order.user.id not in [478, 5506, 11583]:
                                        #add $2 to cancel out some small changes in shipping rate
                                        if D(selected_rate.rate) > order.shipping_excl_tax + D('2.0'):
                                            postage_error = True
                                            easypost_msg = "EasyPost rate > order no margin shipping rate," \
                                                           " order shipping rate = %s, shipment rate = %s"  % \
                                                           (order.shipping_excl_tax, selected_rate.rate)
                                            logger.critical(easypost_msg)
                                if postage_error:
                                    self.refund_shipment(order, package, s, easypost_msg)
                                    postage_errors += 1
                                    #go to the next order
                                    continue

                                package.status = 'postage_purchased'
                                if tracking_number:
                                    order.tracking.tracking_number = tracking_number
                                else:
                                    logger.error("EasyPost - no tracking number available for package %s" % package.upc)
                                order.tracking.shipment_id = shipment.id
                                order.tracking.save()
                                package.save()
                                #the next step is to pay partner's share if needed
                                #otherwise, mark that processing is done
                                if order.partner_waits_for_payment():
                                    self.transfer_payment_to_partner(order)
                                else:
                                    order.set_status('Processed')
                                #download the shipping label
                                #ZPL label can't be converted to PDF / PNG, therefore, no need to ask for those
                                #self.download_shipping_labels(s, order)
                                #commercial invoice is only required for express carriers
                                if order.tracking.carrier in settings.EASYPOST_EXPRESS_CARRIERS:
                                    self.download_commercial_invoices(order, s.forms)
                            else:
                                #change order status so we could pick it up for generating new labels
                                order.set_status('In process')
                                logger.warning("Postage was not purchased for order id: %s" % order.id)
                        else:
                            self.download_commercial_invoices(order, s.forms)
                    #download batch label only if we found at least 1 valid postage
                    if len(sorted_shipments) != postage_errors:
                        #download batch shipping label in zpl format
                        batch_label_url = easypost_batch.label_url
                        file_name = '%s_shipping_labels.zpl' % batch.batch_id
                        batch_shipping_label_file = self.download_file(batch_label_url, '.zpl')
                        batch.shipping_label.save(file_name, batch_shipping_label_file, save=False)
                        batch_shipping_label_file.close()
                        batch.status = ShippingLabelBatch.STATUS.label_generated
                    else:
                        batch.status = ShippingLabelBatch.STATUS.label_refunded
                    batch.save()
                elif easypost_batch.state == 'label_generating':
                    #this can take some time, save status only once
                    if batch.status != ShippingLabelBatch.STATUS.label_generating:
                        batch.status = ShippingLabelBatch.STATUS.label_generating
                        batch.save()
                else:
                    logger.debug("Received batch status: %s" % easypost_batch.state)

            except coreeasypost.Error as e:
                logger.error("EasyPost batch api failed: %s" % e.message)
                if e.param:
                    logger.error('Specifically an invalid param: %s' % e.param)
                #dirty hack for catching weird errors in the progress of generation labels
                #we simply change the state to label_generating to continue where we left
                if 'This batch is either already purchased or currently being purchased' in e.message:
                    batch.status = ShippingLabelBatch.STATUS.label_generating
                else:
                    batch.status = ShippingLabelBatch.STATUS.api_failed
                batch.save()
                #change orders status so we could pick them up for generating new labels
                #batch.orders.all().update(status='In process')

