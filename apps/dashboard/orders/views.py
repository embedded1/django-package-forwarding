from django.views.generic import View, ListView, UpdateView, FormView
from oscar.apps.dashboard.orders.views import OrderListView as CoreOrderListView
from apps.rewards.models import ReferralReward
from apps.customer.mixins import AjaxTemplateMixin
from apps.checkout.forms import ShippingCustomForm
from apps.customer.alerts.senders import send_incomplete_customs_declaration_email
from django.http import HttpResponseRedirect, Http404
from apps.order.models import (
    Order, ShippingLabelBatch
)
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from django.contrib import messages
from decimal import Decimal as D
from django.core.urlresolvers import reverse
from apps.shipping.apis import EasyPostAPI
from apps.checkout import cache
from apps.order.utils import OrderValidator
from django.utils.translation import ugettext as _
from oscar.views import sort_queryset
import easypost as coreeasypost
from django.http import HttpResponse
from apps import utils
import datetime
import os
import zipfile
from StringIO import StringIO
from django.conf import settings
import logging
from oscar.core import ajax
from .forms import (
    ShippingLabelBatchForm, PartialRefundForm,
    OrderSearchForm, BitcoinPaymentsForm)
from django.utils import simplejson as json
from paypal.adaptive.facade import refund_transaction
from paypal import exceptions
from PyPDF2 import PdfFileMerger, PdfFileReader
from apps.user.models import AccountStatus
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, Flowable
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import A4
#from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.barcode import qr
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Drawing
from reportlab.lib.styles import getSampleStyleSheet
import csv

#now = datetime.datetime.utcnow().replace(tzinfo=utc)
#zip_filename = "batch_shipping_labels_%s.zip" % now.strftime("%Y-%m-%d_%H:%M:%S")
#s = self.zip_batches_shipping_labels(batches)
#response = HttpResponse(s.getvalue(), content_type='application/zip')
#response['Content-Disposition'] = 'attachment; filename=%s' % zip_filename
#messages.success(request, "zip file created successfully")

logger = logging.getLogger("management_commands")

class QRFlowable(Flowable):
    """
    Usage: story.append(QRFlowable("http://google.fr"))

    Taken unmodified from SO http://stackoverflow.com/a/18714402
    """

    def __init__(self, qr_value):
        # init and store rendering value
        Flowable.__init__(self)
        self.qr_value = qr_value

    def wrap(self, availWidth, availHeight):
        # optionnal, here I ask for the biggest square available
        self.width = self.height = min(availWidth, availHeight)
        return self.width, self.height

    def draw(self):
        # here standard and documented QrCodeWidget usage on
        # Flowable canva
        qr_code = qr.QrCodeWidget(self.qr_value)
        bounds = qr_code.getBounds()
        qr_width = bounds[2] - bounds[0]
        qr_height = bounds[3] - bounds[1]
        w = float(self.width)
        d = Drawing(w, w, transform=[w/qr_width, 0, 0, w/qr_height, 0, 0])
        d.add(qr_code)
        renderPDF.draw(d, self.canv, 0, 0)

class BatchListView(ListView):
    """
    Dashboard view for a list of shipping label batches.
    Supports the permission-based dashboard.
    """
    model = ShippingLabelBatch
    context_object_name = 'batches'
    form_class = ShippingLabelBatchForm
    template_name = 'dashboard/orders/batch_list.html'
    paginate_by = 25

    def get_context_data(self, **kwargs):
        ctx = super(BatchListView, self).get_context_data(**kwargs)
        ctx['queryset_description'] = "Shipping label batches"
        ctx['form'] = self.form_class(self.request.GET)
        return ctx

    def get_queryset(self):  # noqa (too complex (19))
        """
        Build the queryset for this list.
        """
        queryset = super(BatchListView, self).get_queryset()
        form = self.form_class(self.request.GET)
        if form.is_valid():
            data = form.cleaned_data
            if data.get('batch_id'):
                return queryset.filter(batch_id=data['batch_id'])
            if data.get('status'):
                return queryset.filter(status=data['status'])

        queryset = sort_queryset(queryset, self.request, ['status',], default='-date_created')
        return queryset


class BatchUpdateView(UpdateView):
    template_name = 'dashboard/orders/batch_form.html'
    model = ShippingLabelBatch
    form_class = ShippingLabelBatchForm

    def get_context_data(self, **kwargs):
        ctx = super(BatchUpdateView, self).get_context_data(**kwargs)
        ctx['title'] = _("Update batch '%s'") % self.object.batch_id
        return ctx

    def get_success_url(self):
        messages.info(self.request, _("Batch updated successfully"))
        return reverse("dashboard:batch-list")


class GenerateShippingLabelsView(View):
    fragment = 'report_type=packages_ready_for_shipping_label&date_from=&date_to='
    label_url = None

    def get(self, request, *args, **kwargs):
        return self.reload_page_response()

    def post(self, request, *args, **kwargs):
        # Look for orders to generate shipping labels to
        order_ids = request.POST.getlist('selected_line')
        orders_qs = Order.objects.select_related(
            'tracking', 'package', 'user',
            'package__customs_form').prefetch_related(
            'package__stockrecords',
            'package__stockrecords__partner').filter(id__in=order_ids)

        orders = list(orders_qs)
        if len(orders) == 0:
            messages.error(request, _("No orders selected"))
            return self.reload_page_response()

        #1 - Go over all selected orders and create new shipment
        #2 - create and buy shipping labels for selected orders
        #3 - poll till we get the shipping label url
        #4 - download shipping labels pdf file
        #5 - save tracking number for each package
        #6 - mark order as "Processed"
        #7 - mark package status as "Shipped"
        easypost = EasyPostAPI()
        shipments = []
        for order in orders:
            try:
                customs_form = order.package.customs_form
            except ObjectDoesNotExist:
                customs_form = None

            shipment_kwargs = {
                'package_upc': order.package.upc,
                'shipping_addr': order.shipping_address,
                'weight': D(order.package.weight),
                'length': D(order.package.length),
                'width': D(order.package.width),
                'height': D(order.package.height),
                'carrier': order.tracking.carrier,
                'service': order.shipping_code,
                'customs_form': customs_form,
                'customer_name': order.user.get_full_name(),
                'customer_uuid': order.user.get_profile().uuid,
                'email': order.user.email,
                'partner': order.package.partner,
                'itn_number': order.tracking.itn_number,
                'contents_explanation': order.tracking.contents_explanation,
                'lithium_battery_exists': order.package.is_contain_lithium_battery
            }

            shipment = easypost.create_shipment(**shipment_kwargs)

            if shipment is not None:
                shipments.append(shipment)

        #create the batch and wait for the cronjob task to complete the process in the background
        if shipments:
            try:
                batch = easypost.create_batch_and_buy(shipments=shipments)
            except coreeasypost.Error as e:
                logger.error("EasyPost create_batch_and_buy failed: %s" % e.message)
                if e.param:
                    logger.error('Specifically an invalid param: %s' % e.param)
                messages.error(request, _("An error occurred while generating shipping labels,"
                                          " please contact admin before proceeding."))
            else:
                #add the batch id to db for the cronjob to pick it up
                shipping_label_batch = ShippingLabelBatch.objects.create(
                    batch_id=batch.id,
                    partner=orders[0].package.partner)
                #add selected orders
                shipping_label_batch.orders.add(*orders)
                #change order status to generating_label - this will be changed by cronjob
                orders_qs.update(status='Purchasing label')
                messages.success(request, _(
                    "Shipping labels for the selected orders are being purchased in the background"))
        else:
            messages.error(request, _("No shipment created, please contact admin"))
        return self.reload_page_response()

    def reload_page_response(self):
        url = reverse('dashboard:reports-index')
        if self.fragment:
            url += '?' + self.fragment
        return HttpResponseRedirect(url)


class PrintShippingLabelsView(View):
    fragment = 'report_type=print_shipping_labels&date_from=&date_to='
    label_url = None

    def get(self, request, *args, **kwargs):
        return self.reload_page_response()

    def reload_page_response(self):
        url = reverse('dashboard:reports-index')
        if self.fragment:
            url += '?' + self.fragment
        return HttpResponseRedirect(url)

    def zip_batches_shipping_labels(self, batches):
        zip_subdir = 'batches'
        # Open StringIO to grab in-memory ZIP contents
        s = StringIO()

        # The zip compressor
        zf = zipfile.ZipFile(s, "w")

        for batch in batches:
            fpath = batch.shipping_label.path
            # Calculate path for file in zip
            fdir, fname = os.path.split(fpath)
            zip_path = os.path.join(zip_subdir, fname)
            # Add file, at correct path
            zf.write(fpath, zip_path)

        # Must close zip for all contents to be written
        zf.close()
        return s

    def concat_batch_commercial_invoices(self, commercial_invoices):
        merger = PdfFileMerger()
        commercial_invoices_pdf_name = 'commercial_invoices.pdf'
        commercial_invoices_pdf_path = os.path.join(
            settings.MEDIA_ROOT,
            settings.COMMERCIAL_INVOICE_ZIP_FOLDER,
            commercial_invoices_pdf_name)
        for commercial_invoice in commercial_invoices:
            merger.append(PdfFileReader(file(commercial_invoice.original.path, 'rb')))
        # Must close zip for all contents to be written
        merger.write(file(commercial_invoices_pdf_path, 'wb'))
        return os.path.join(
            settings.MEDIA_URL,
            settings.COMMERCIAL_INVOICE_ZIP_FOLDER,
            commercial_invoices_pdf_name)

    def collect_data(self, batches):
        data = []
        site_prop = utils.get_site_properties()
        for batch in batches.all():
            for _ in batch.orders.all():
                data.append({
                    'h1': "Give $5, Get $5",
                    'text1': "Share your promo code with friends and they will get $5 off their first order.",
                    'text2': "Once they've tried USendHome, you'll automatically get $5 in shipping credits.",
                    'text3': "Scan the code and start earning credits now!",
                    'url': site_prop['site'] + reverse('customer:referrals-index')
                })
        return data

    @staticmethod
    def generate_row(row):
        """ Returns a table story for given row of data """

        # I use style sheet provided by reportlab
        # instead, we can make our own
        styles = getSampleStyleSheet()
        styles['Normal'].leading = 24

        # inner table with h1 and text
        text_template = u'<font size=16><b>{}</b></font><br/><font size=10>{}<br/>{}<br/>{}</font>'
        text_table = Table(
            [[
                Paragraph(text_template.format(row['h1'], row['text1'], row['text2'], row['text3']), styles['Normal'])
            ]],
            rowHeights=[4*cm],
            style=TableStyle([
                ('TOPPADDING', (0, 0), (0, 0), 10),
                ('BOTTOMPADDING', (0, 0), (0, 0), 0),
                ('VALIGN', (0, 0), (0, 0), 'TOP'),

                ('TOPPADDING', (1, 0), (0, 0), 0),
                ('BOTTOMPADDING', (1, 0), (0, 0), 2*cm),
                ('VALIGN', (1, 0), (0, 0), 'TOP'),

                # debug grids
                # ('GRID', (0, 0), (-1, -1), 0, colors.blue),
            ])
        )

        # outter table with QR code and text_table
        table = Table(
            [[
                QRFlowable(row['url']),
                text_table
            ]],
            colWidths=[4*cm, 14*cm],
            rowHeights=[4*cm],
            style=TableStyle([
                # disable padding
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),

                # debug grids
                # ('GRID', (0, 0), (0, 0), 0, colors.green),
            ])
        )

        return table

    def generate_pdf(self, data, buff):
        """ Generates a PDF """
        # initialize the PDF object
        pdf = SimpleDocTemplate(buff, pagesize=A4,
            rightMargin=1*cm, leftMargin=1*cm, topMargin=1*cm, bottomMargin=1*cm)

        # register fonts here
        # I've left it commented out and it works with default font
        # 2nd argument to TTFont is full file path, in this example
        # file was within current directory
        # pdfmetrics.registerFont(TTFont('Helvetica', 'helveticaneueltpro-cn-webfont.ttf'))

        # a list of stories
        stories = []

        for x in data:
            # generate row, ensure it does not break with page breaks
            # with KeepTogether
            stories.append(KeepTogether(self.generate_row(x)))
            # after each row, add vertical space
            stories.append(Spacer(1, 2*cm))

        # generate pdf
        pdf.build(stories)

    def post(self, request, *args, **kwargs):
        batches_ids = request.POST.getlist('selected_line')
        batches = ShippingLabelBatch.objects\
            .prefetch_related('orders', 'orders__user')\
            .filter(pk__in=batches_ids)

        if batches.exists():
            if 'referral-codes' in request.POST:
                response = HttpResponse(mimetype='application/pdf')
                pdf_name = "referral-codes.pdf"
                response['Content-Disposition'] = 'attachment; filename=%s' % pdf_name
                data = self.collect_data(batches)
                buff = StringIO()
                self.generate_pdf(data, buff)
                response.write(buff.getvalue())
                buff.close()
                return response
            else:
                #update batches status to label_printed
                batches.update(status=ShippingLabelBatch.STATUS.label_printed)
                messages.success(request, "Batches updated successfully")
        else:
            messages.info(request, "No batch selected")
        return self.reload_page_response()

    def json_response(self, payload):
        return HttpResponse(json.dumps(payload),
                            mimetype="application/json")

class IncompleteCustomsDeclarationNotificationView(View):
    def dispatch(self, request, *args, **kwargs):
        self.order = get_object_or_404(Order, pk=request.POST.get('order_pk'))
        return super(IncompleteCustomsDeclarationNotificationView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.order.is_incomplete_customs_declaration = True
        self.order.save()
        send_incomplete_customs_declaration_email(self.order)
        messages.success(request, "Email was successfully sent to the customer")
        redirect_url = self.request.META.get('HTTP_REFERER', reverse('dashboard:index'))
        return HttpResponseRedirect(redirect_url)

class AddITNNumberView(View):
    def dispatch(self, request, *args, **kwargs):
        try:
            self.order = Order.objects\
                .select_related('tracking')\
                .get(pk=request.POST.get('order_pk'))
        except Order.DoesNotExist:
            raise Http404('No order matches the given query.')
        return super(AddITNNumberView, self).dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        itn_number = request.POST.get('itn_number')
        if itn_number:
            self.order.tracking.itn_number = itn_number
            self.order.tracking.save()
            messages.success(request, "ITN number was successfully added")
        else:
            messages.error(request, "No ITN number given")
        redirect_url = self.request.META.get('HTTP_REFERER', reverse('dashboard:generate-shipping-labels'))
        return HttpResponseRedirect(redirect_url)

class UpdateCustomsDeclarationView(FormView):
    form_class = ShippingCustomForm
    num_of_items = 15
    template_name = 'dashboard/orders/customs_declaration.html'

    def dispatch(self, request, *args, **kwargs):
        try:
            self.order = Order.objects\
                .select_related('package')\
                .prefetch_related('package__customs_form', 'package__customs_form__items')\
                .get(pk=kwargs['pk'])
            self.package = self.order.package
        except Order.DoesNotExist:
            raise Http404('No order matches the given query.')
        return super(UpdateCustomsDeclarationView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super(UpdateCustomsDeclarationView, self).get_context_data(**kwargs)
        ctx['title'] = _("Update customs declaration for package '#%s'") % self.package.upc
        return ctx

    def get_form_kwargs(self):
        kwargs = super(UpdateCustomsDeclarationView, self).get_form_kwargs()
        kwargs['package'] = self.package
        kwargs['num_of_items'] = self.num_of_items
        kwargs['is_readonly'] = False
        kwargs['include_hs_tariff_number_fields'] = True
        kwargs['missing_value'] = False
        return kwargs

    def get_initial(self):
        """
        Populate the custom form declaration with previous data (if any)
        """
        return self.package.customs_form_data()

    def form_valid(self, form):
        #save object to db
        form.save()
        #mark that customs declaration is now complete
        self.order.is_incomplete_customs_declaration = False
        self.order.save()
        return super(UpdateCustomsDeclarationView, self).form_valid(form)

    def get_success_url(self):
        # loose batteries can't be shipped from the USA, need to redirect back
        # to pending packages page with an proper message
        messages.success(self.request, "Customs declaration updated")
        redirect_url = self.request.META.get('HTTP_REFERER', reverse('dashboard:generate-shipping-labels'))
        return redirect_url

class DownloadReturnLabelsView(View):
    fragment = 'report_type=download_return_label&date_from=&date_to='
    label_url = None

    def get(self, request, *args, **kwargs):
        return self.reload_page_response()

    def reload_page_response(self):
        url = reverse('dashboard:reports-index')
        if self.fragment:
            url += '?' + self.fragment
        return HttpResponseRedirect(url)

    def zip_return_labels(self, orders):
        #we need to created a zip file from selected shipping labels
        now = datetime.datetime.now()
        zip_filename = "return_labels_%s.zip" % now.strftime("%Y-%m-%d_%H:%M:%S")
        zip_full_path = os.path.join(settings.MEDIA_ROOT, settings.RETURN_LABEL_ZIP_FOLDER)
        try:
            os.makedirs(zip_full_path)
        except OSError:
            if not os.path.isdir(zip_full_path):
                raise
        # The zip compressor
        zf = zipfile.ZipFile(os.path.join(zip_full_path, zip_filename), "w")
        for order in orders:
            package = order.package
            fpath = order.latest_shipping_label().original.path
            # Calculate path for file in zip
            fdir, fname = os.path.split(fpath)
            zip_subdir = 'package-id-%s' % package.upc
            #we create a subdir that contains package id for package identification
            zip_path = os.path.join(zip_subdir, fname)
            # Add file, at correct path
            zf.write(fpath, zip_path)
        # Must close zip for all contents to be written
        zf.close()
        return os.path.join(settings.MEDIA_URL, settings.RETURN_LABEL_ZIP_FOLDER, zip_filename)

    def post(self, request, *args, **kwargs):
        if request.is_ajax():
            payload = {}
            flash_messages = ajax.FlashMessages()
            orders_ids = request.POST.getlist('selected_line')
            orders = list(Order.objects.select_related('package').filter(id__in=orders_ids))
            if len(orders):
                payload['download_url'] = self.zip_return_labels(orders)
                flash_messages.success("zip file created successfully")
                self.change_orders_status_to_shipped(orders)
            else:
                flash_messages.info("No orders selected")
            return self.json_response(flash_messages, payload)

        return self.reload_page_response()

    def json_response(self, flash_messages, payload):
        payload['messages'] = flash_messages.to_json()
        return HttpResponse(json.dumps(payload),
                            mimetype="application/json")

    def change_orders_status_to_shipped(self, orders):
        for order in orders:
            if order.partner_waits_for_payment():
                order.set_status('Pending partner payment')
            else:
                order.set_status('Shipped')

class OrderRefundView(AjaxTemplateMixin, FormView):
    form_class = PartialRefundForm
    ajax_template_name = 'dashboard/orders/partials/order_partial_refund_inner.html'

    def dispatch(self, request, *args, **kwargs):
        self.order = get_object_or_404(Order, pk=kwargs['pk'])
        return super(OrderRefundView, self).dispatch(request, *args, **kwargs)

    def get_template_names(self):
        refund_type = self.kwargs['refund_type']
        if refund_type == 'full':
            return ['dashboard/orders/partials/order_full_refund_inner.html']
        if refund_type == 'partial':
            return ['dashboard/orders/partials/order_partial_refund_inner.html']
        if refund_type == 'cancel':
            return ['dashboard/orders/partials/order_cancel_inner.html']
        if refund_type == 'approve':
            return ['dashboard/orders/partials/order_approve_inner.html']
        if refund_type == 'validate':
            return ['dashboard/orders/partials/order_validate_inner.html']
        return [self.ajax_template_name]

    def get_receivers(self, total_amount, secondary_amount):
        """
        This function returns the payment receivers, we support 2 options:
        1 - Order payment is split between USendHome and the partner, in that case
            we calculate partner's share
        2 - Order payment isn't split and transferred as a whole to USendHome
        To determine in what option are we, we check if PartnerOrderPaymentSettings object
        is available for package's partner, if it exists, we follow it and divide the payment
        between UsendHome and the partner, otherwise, we take it all.
        """
        receivers = []

        if total_amount:
            receivers.append({
                'email': settings.PAYPAL_PRIMARY_RECEIVER_EMAIL,
                'amount': total_amount
            })

        if secondary_amount:
            #Find out if we need to transfer funds to partner
            partner = self.order.package.stockrecords.all()\
                .prefetch_related('partner', 'partner__payments_settings')[0].partner
            partner_order_payment_settings = partner.active_payment_settings
            if partner_order_payment_settings:
                receivers.append({
                    'email': partner_order_payment_settings.billing_email,
                    'amount': secondary_amount
                })
        return receivers

    def issue_refund(self, total_amount=None, secondary_amount=None):
        logger.info("Issuing full refund to order #%s" % self.order.number)
        pay_key = self.order.get_pay_key()
        try:
            receivers = self.get_receivers(total_amount, secondary_amount)
            refund_transaction(pay_key, receivers)
        except exceptions.PayPalError:
            logger.critical("Issuing refund to order #%s failed" % self.order.number)
            return False
        return True

    def get_success_url(self):
        return self.request.META.get('HTTP_REFERER', reverse('dashboard:index'))

    def get_form_kwargs(self):
        kwargs = super(OrderRefundView, self).get_form_kwargs()
        kwargs['order'] = self.order
        return kwargs

    def return_refunded_order_referral_credit(self, order):
        """
        This function returns back the referral credit for cancelled orders
        """
        ReferralReward.objects\
            .filter(order=order,
                    is_active=True,
                    date_redeemed__isnull=False)\
            .update(date_redeemed=None)

    def get_context_data(self, **kwargs):
        ctx = super(OrderRefundView, self).get_context_data(**kwargs)
        ctx['pk'] = self.order.pk
        return ctx

    def post(self, request, *args, **kwargs):
        refund_type = self.kwargs['refund_type']
        if refund_type == 'full':
            if self.issue_refund():
                #change order status to refunded
                self.order.set_status('Refunded')
                #return referral credit back to the user
                self.return_refunded_order_referral_credit(self.order)
                #update amount_refunded attribute
                self.order.sources.all().update(amount_refunded=self.order.total_incl_tax)
                #Readd package back to user control panel if we successfully refunded the order
                package = self.order.package
                package.status = 'pending'
                package.save()
                messages.success(self.request, _("Refund successfully submitted"))
            else:
                messages.success(self.request, _("Refund failed!"))
            return self.json_response(is_valid=True, redirect_url=self.get_success_url())
        elif refund_type == 'partial':
            form_class = self.get_form_class()
            form = self.get_form(form_class)
            if form.is_valid():
                return self.form_valid(form)
            else:
                return self.form_invalid(form)
        elif refund_type == 'cancel':
            self.order.set_status('Cancelled')
            cancelled_reason = 'Order manually cancelled'
            OrderValidator().cancel_order(
                order=self.order,
                key=self.order.get_pay_key(),
                cancelled_reason=cancelled_reason,
                suspend_account=False)
            messages.success(request, _("Order successfully cancelled, full refund issued"))
            return self.json_response(is_valid=True, redirect_url=self.get_success_url())
        elif refund_type == 'approve':
            if self.order.status not in ["Pending", "Pending fraud check"]:
                messages.success(request, _("Order already approved"))
            else:
                if self.order.status == 'Pending fraud check':
                    #mark account as verified
                    obj, created = AccountStatus.objects.get_or_create(
                        profile=self.order.user.get_profile(),
                        defaults={'verification_status': AccountStatus.VERIFIED}
                    )
                    if not created:
                        obj.verification_status = AccountStatus.VERIFIED
                        obj.save()

                #we skip validations to get this order approved after manual review
                pay_key = self.order.get_pay_key()
                OrderValidator().validate_order(
                    order=self.order, key=pay_key,
                    skip_validation=True)

                messages.success(request, _("Order successfully approved"))

            return self.json_response(is_valid=True, redirect_url=self.get_success_url())
        #elif refund_type == 'validate':
        #    process_order(self.order)
        #    messages.success(request, _("Order is being validated in the background"))
        #    return self.json_response(is_valid=True, redirect_url=self.get_success_url())
        else:
            messages.error(self.request, _("Invalid refund type"))
            return self.json_response(is_valid=True, redirect_url=self.get_success_url())

    def form_invalid(self, form):
        ctx = self.get_context_data(form=form)
        if self.request.is_ajax():
            return self.json_response(ctx=ctx)
        return self.render_to_response(ctx)

    def form_valid(self, form):
        total_amount = form.cleaned_data['total_amount']
        if self.issue_refund(
            total_amount=total_amount,
            secondary_amount=form.cleaned_data['secondary_receiver_amount']):
            #update amount_refunded attribute
            self.order.sources.all().update(amount_refunded=total_amount)
            messages.success(self.request, _("Partial refund successfully submitted"))
        else:
            messages.success(self.request, _("Partial refund failed!"))
        return self.json_response(is_valid=True, redirect_url=self.get_success_url())


class OrderListView(CoreOrderListView):
    form_class = OrderSearchForm

    def get_queryset(self):
        queryset = super(OrderListView, self).get_queryset()
        data = getattr(self.form, 'cleaned_data', None)
        if not data:
            self.form = self.form_class(self.request.GET)
            if not self.form.is_valid():
                return queryset
        data = self.form.cleaned_data
        if data['maxmind_trans_id']:
            queryset = queryset.filter(maxmind_trans_id=data['maxmind_trans_id'])
        return queryset

class ProcessBitcoinPaymentsView(FormView):
    form_class = BitcoinPaymentsForm

    @staticmethod
    def is_payment_received_in_full(balance):
        return not balance > D('3.0')

    def process_payment(self, basket_id, amount_debited, error_orders):
        order = Order.objects.get(basket_id=basket_id)
        source = order.get_payment_source()
        #update amount_debited field
        source.amount_debited = D(amount_debited)
        if self.is_payment_received_in_full(source.balance):
            source.save()
        else:
            error_orders.append(order.number)

    def mark_partner_paid(self, orders_numbers):
        if orders_numbers:
            orders = Order.objects.filter(number__in=orders_numbers)
            for order in orders:
                source = order.get_payment_source()
                source.partner_paid = True
                source.save()

    def form_valid(self, form):
        """
        Process the CSV file and update the amount_debit of each order
        """
        if form.cleaned_data.get('payments_file'):
            error_orders = []
            csvfile = form.cleaned_data['payments_file']
            reader = csv.DictReader(csvfile)

            for row in reader:
                basket_id = row.get('txid')
                amount_debited = row.get('usd_amount')
                if basket_id and amount_debited:
                    basket_id = basket_id.strip()
                    amount_debited = amount_debited.strip()[1:] #trim the $ sign
                    self.process_payment(basket_id, amount_debited, error_orders)

            if error_orders:
                error_orders_str = ",".join(error_orders)
                messages.error(self.request,
                               "Payment hasn't received in full for orders: %s" % error_orders_str)
            else:
                messages.success(self.request,
                                 "All payments have completed in full")
        elif form.cleaned_data.get('partner_paid'):
            orders_numbers = form.data.get('orders', "").split(',')
            #"get rid of the # character
            orders_numbers = [num[1:] for num in orders_numbers]
            self.mark_partner_paid(orders_numbers)
            messages.success(self.request,
                             "Partner paid was successfully applied to %d orders" % len(orders_numbers))
        return super(ProcessBitcoinPaymentsView, self).form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Errors in form")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return self.request.META.get('HTTP_REFERER', reverse('dashboard:index'))






