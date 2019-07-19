from django.views.generic import View
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import logging
import json
from .tasks import (
    easypost_tracking_details_handler,
    paypal_ipn_transaction_handler,
    bitcoin_ipn_transaction_handler,
    bitcoinpay_ipn_transaction_handler)

logger = logging.getLogger("management_commands")

class EasyPostTrackerWebHookView(View):
    http_method_names = ['post']

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super(EasyPostTrackerWebHookView, self).dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        #send the hard work to the background worker
        try:
            data = request.POST.keys()[0]
        except IndexError:
            #no data, maybe false alarm
            #bail out
            pass
        else:
            easypost_tracking_details_handler.apply_async(
                kwargs={'data': data},
                queue='webhooks')
        return HttpResponse(status=200)

class PayPalIPNView(View):
    http_method_names = ['post']

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super(PayPalIPNView, self).dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        #send the hard work to the background worker
        try:
            data = dict(request.POST.items())
        except AttributeError:
            #no data, maybe false alarm
            #bail out
            pass
        else:
            paypal_ipn_transaction_handler.apply_async(
                kwargs={'raw_message': request.body, 'data': data},
                queue='webhooks')
        return HttpResponse(status=200)

class BitcoinIPNView(View):
    http_method_names = ['post']

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super(BitcoinIPNView, self).dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        #send the hard work to the background worker
        try:
            data = dict(request.POST.items())
        except AttributeError:
            #no data, maybe false alarm
            #bail out
            pass
        else:
            bitcoin_ipn_transaction_handler.apply_async(
                kwargs={'raw_message': request.body, 'data': data},
                queue='webhooks')
        return HttpResponse(status=200)

class BitcoinpayIPNView(View):
    http_method_names = ['post']

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super(BitcoinpayIPNView, self).dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        #send the hard work to the background worker
        try:
            data = json.loads(request.body)
            req_sig = request.META.get('HTTP_BPSIGNATURE', '')
        except Exception:
            #no data, maybe false alarm
            #bail out
            pass
        else:
            #bitcoinpay_ipn_transaction_handler(request.body, data, req_sig)
            bitcoinpay_ipn_transaction_handler.apply_async(
                kwargs={'raw_message': request.body, 'data': data, 'req_sig': req_sig},
                queue='webhooks')
        return HttpResponse(status=200)
