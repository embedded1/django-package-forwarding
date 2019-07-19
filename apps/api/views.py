from django.views.generic import View
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from collections import OrderedDict
#from apps.address.utils import get_us_state_code
from django.conf import settings
from apps.tasks.mixins import CeleryTaskStatusMixin
from django.template.loader import render_to_string
from django.http import HttpResponseBadRequest
from django.template import RequestContext
from django.db.models import F
from .forms import PackageForwardingAccountForm
from apps.static.models import Statistics
from .generators import ForwardingAddressGenerator
from apps.shipping.tasks import get_shipping_rates_chrome
from django.views.generic import FormView
from django.contrib import messages
import simplejson as json
import logging

logger = logging.getLogger("management_commands")


class ForwardingAddressAPIView(ForwardingAddressGenerator, View):
    http_method_names = ['post']

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super(ForwardingAddressAPIView, self).dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except Exception:
            data = {}
        addresses, status_code = self.generate_address(data)
        if status_code in [200, 201]:
            payload = {
                'addresses': addresses
            }
            if not addresses:
                payload['error_msg'] = "missing data"
            return self.send_response(payload, status_code)
        return HttpResponseForbidden()

    def send_response(self, payload, status=200):
        return HttpResponse(json.dumps(payload),
                            mimetype="application/json",
                            status=status)

class ChromeAmazonShippingMethodsView(View, CeleryTaskStatusMixin):
    template = "api/chrome/shipping_methods.html"
    http_method_names = ['post', 'get']

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super(ChromeAmazonShippingMethodsView, self).dispatch(*args, **kwargs)

    def collect_bins_shipping_methods(self, data, **kwargs):
        total_num_of_items = 0
        bins = []

        ret = {
            'no_data_items': data[0],
            'country': data[1].printable_name,
        }

        for bin in data[2:]:
            bins.append({
                'methods': bin['methods'],
                'packages': bin['packages']
            })
            total_num_of_items += len(bin['packages'])

        ret['bins'] = bins
        ret['total_num_of_items'] = total_num_of_items
        return ret

    def collect_general_shipping_messages(self):
        for tag, gen_msg in settings.GENERAL_MESSAGES:
            messages.add_message(self.request, tag, gen_msg)

    def handle_celery_task_result(self, res):
        if not res:
            return HttpResponse(
                json.dumps({'status': 'FAILURE'}),
                mimetype="application/json")
        ctx = self.collect_bins_shipping_methods(res)
        ctx['forwarding_address_exists'] = self.forwarding_address_exists
        if ctx['bins']:
            self.collect_general_shipping_messages()
        content_html = render_to_string(
            self.template,
            RequestContext(self.request, ctx))
        return HttpResponse(json.dumps({
                'status': 'COMPLETED',
                'content_html': content_html}),
                mimetype="application/json")

    def get(self, request, *args, **kwargs):
        #poll task state
        task_id = request.GET.get('task_id')
        self.forwarding_address_exists = request.GET.get(
            'forwarding_address_exists', 'false')
        if task_id:
            return self.task_status(task_id)
        return HttpResponse()

    def increase_usage_counter(self):
        Statistics.objects\
            .filter(name='chrome')\
            .update(usage_counter=F('usage_counter') + 1)

    def post(self, request, *args, **kwargs):
        payload = {}
        #send the hard work to the background worker
        try:
            data = dict(request.POST.items())
        except AttributeError:
            #no data, maybe false alarm
            #bail out
            pass
        else:
            #as usual, let celery handle all the hard work :)
            kwargs = {
                'items': json.loads(data.get('items', '{}')),
                'to_country': data.get('to_country'),
                'postcode': data.get('postcode', None),
                'city': data.get('city', None),
                'include_usps': data.get('include_usps', 'false'),
            }
            task = get_shipping_rates_chrome(**kwargs)
            payload['task_id'] = task.id
            self.increase_usage_counter()
        return HttpResponse(json.dumps(payload), mimetype="application/json")


class ForwardingAddressCreateView(ForwardingAddressGenerator, FormView):
    http_method_names = ['post']
    form_class = PackageForwardingAccountForm

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super(ForwardingAddressCreateView, self).dispatch(*args, **kwargs)

    def post(self, request, *args, **kwargs):
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        issuer = request.POST.get('issuer')
        password = request.POST.get('password')
        ctx = {}
        form = self.get_form(self.form_class)

        if not form.is_valid():
            ctx['form'] = form
            ctx['issuer'] = issuer
            return self.json_response(request, ctx, 'api/address/form.html')

        data = {
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'password': password,
            'issuer': issuer
        }
        #sign the payload
        #signature = self.calculate_signature(data, issuer)
        #data['signature'] = signature

        addresses, status_code = self.generate_address(data)
        ctx['addresses'] = addresses
        if status_code in [200, 201]:
            return self.json_response(request, ctx,
                                      'api/address/forwarding.html',
                                      addresses=addresses)
        return HttpResponseBadRequest()

    def json_response(self, request, ctx, html_template, **kwargs):
        payload = kwargs
        if ctx:
            content_html = render_to_string(
                html_template,
                RequestContext(request, ctx))
            payload.update({'content_html': content_html})
        return HttpResponse(json.dumps(payload),
                            mimetype="application/json")



