from django.views.generic import FormView
from apps.shipping_calculator.forms import (
    ShippingCalculatorForm,
    AmazonShippingCalculatorForm
)
from apps.tasks.mixins import CeleryTaskStatusMixin
from apps.shipping import tasks
from django.core.urlresolvers import reverse
from decimal import Decimal as D, ROUND_UP
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.template import RequestContext
from django.utils import simplejson as json
from oscar.core import ajax
from apps.tasks.utils import ShippingMethodsHandler
from apps.customer.tasks import mixpanel_track_calculator
import logging


logger = logging.getLogger("management_commands")


class ShippingCalculatorView(FormView, ShippingMethodsHandler, CeleryTaskStatusMixin):
    form_class = ShippingCalculatorForm
    template_name = 'calculators/package.html'
    shipping_methods_template_name = 'calculators/basic_calculator_search_results.html'
    calculator_form_template_name = 'calculators/partials/basic_calculator_form.html'

    def two_digits_quantize(self, res):
        return res.quantize(D('.01'), ROUND_UP)

    def convert_kg_to_lbs(self, kg):
        res = kg * D('2.20462')
        return self.two_digits_quantize(res)

    def convert_cm_to_inch(self, cm):
        res = cm * D('0.393701')
        return self.two_digits_quantize(res)

    def handle_celery_task_result(self, result):
        flash_messages = ajax.FlashMessages()
        methods = result.pop('methods', None)
        msgs = result.pop('flash_messages')
        if methods:
            self.collect_general_shipping_messages(msgs)
        self.add_flash_messages(flash_messages, msgs)
        ctx = {'methods': methods}
        return self.shipping_methods_json_response(
            request=self.request,
            ctx=ctx,
            flash_messages=flash_messages,
            html_template=self.shipping_methods_template_name,
            status='COMPLETED',
            is_valid=True)

    def get(self, request, *args, **kwargs):
        if request.is_ajax():
            task_id = request.GET.get('task_id')
            if task_id:
                return self.task_status(task_id)
        return super(ShippingCalculatorView, self).get(request, *args, **kwargs)

    def form_valid(self, form):
        """
        trigger shipping methods worker and show spinner
        """
        if self.request.is_ajax():
            cleaned_data = form.cleaned_data
            weight_units = cleaned_data.get("weight_units", 'lbs')
            dimension_units = cleaned_data.get("dimension_units", 'in')

            if dimension_units == 'cm':
                width, length, height = (
                    self.convert_cm_to_inch(cleaned_data['width']),
                    self.convert_cm_to_inch(cleaned_data['length']),
                    self.convert_cm_to_inch(cleaned_data['height']))
            else:
                width, length, height = (
                    cleaned_data['width'],
                    cleaned_data['length'],
                    cleaned_data['height'])

            if weight_units == 'kg':
                weight = self.convert_kg_to_lbs(cleaned_data['weight'])
            else:
                weight = cleaned_data['weight']
            value = cleaned_data['value']

            #trigger background worker to retrieve shipping methods
            kwargs = {
                'weight': weight,
                'length': length,
                'width': width,
                'height': height,
                'to_country': cleaned_data['country'],
                'city': cleaned_data.get('city', ''),
                'value': value,
                'postcode': cleaned_data.get('postcode', ''),
                'user': self.request.user if self.request.user.is_authenticated() else None
            }
            #get shipping methods
            task = tasks.get_shipping_rates(**kwargs)
            #track calculator usage
            data = {
                'user_id': self.request.user.id if self.request.user.is_authenticated()
                            else cleaned_data.get('mixpanel_anon_id'),
                'calculator_type': 'Package',
                'event_type': 'Package Calculator Run',
                'weight': str(weight),
                'length': str(length),
                'width': str(width),
                'height': str(height),
                'value': str(value),
                'postcode': cleaned_data.get('postcode', ''),
                'city': cleaned_data.get('city', ''),
                'toCountry': cleaned_data['country'].name,
                'weightUnits': weight_units,
                'dimensionUnits': dimension_units
            }
            mixpanel_track_calculator.apply_async(kwargs=data, queue='analytics')
            return self.shipping_methods_json_response(
                request=self.request,
                ctx=None,
                flash_messages=None,
                task_id=task.id,
                country_code=cleaned_data['country'].iso_3166_1_a2,
                status='RUNNING',
                is_valid=True)

        return super(ShippingCalculatorView, self).form_valid(form)

    def form_invalid(self, form):
        if self.request.is_ajax():
            ctx = self.get_context_data(form=form)
            return self.json_response(
                ctx=ctx,
                html_template=self.calculator_form_template_name,
                is_valid=False)
        return super(ShippingCalculatorView, self).form_invalid(form)

    def json_response(self, ctx, html_template, **kwargs):
        payload = kwargs
        calculator_html = render_to_string(
            html_template,
            RequestContext(self.request, ctx))
        payload.update({'content_html': calculator_html})
        return HttpResponse(json.dumps(payload),
                            mimetype="application/json")

    def get_success_url(self):
        return reverse('calculators:package')


class AmazonShippingCalculatorView(FormView, ShippingMethodsHandler, CeleryTaskStatusMixin):
    form_class = AmazonShippingCalculatorForm
    template_name = 'calculators/amazon.html'
    shipping_methods_template_name = 'calculators/amazon_calculator_search_results.html'
    calculator_form_template_name = 'calculators/partials/amazon_calculator_form.html'

    def handle_celery_task_result(self, result):
        flash_messages = ajax.FlashMessages()
        msgs = result.pop('flash_messages')
        if result and result.get('methods'):
            self.collect_general_shipping_messages(msgs)
        self.add_flash_messages(flash_messages, msgs)
        return self.shipping_methods_json_response(
            request=self.request,
            ctx=result,
            flash_messages=flash_messages,
            html_template=self.shipping_methods_template_name,
            status='COMPLETED',
            is_valid=True)

    def get(self, request, *args, **kwargs):
        if request.is_ajax():
            task_id = request.GET.get('task_id')
            if task_id:
                return self.task_status(task_id)
        return super(AmazonShippingCalculatorView, self).get(request, *args, **kwargs)

    def form_valid(self, form):
        """
        run task in the background to fetch shipping methods
        """
        if self.request.is_ajax():
            cleaned_data = form.cleaned_data
            kwargs = {
                'product_url': cleaned_data['product_url'],
                'to_country': cleaned_data['country'],
                'city': cleaned_data.get('city', ''),
                'postcode': cleaned_data.get('postcode', ''),
                'user': self.request.user if self.request.user.is_authenticated() else None
            }
            #get shipping methods
            task = tasks.get_shipping_rates_amazon(**kwargs)
            #track calculator usage
            data = {
                'user_id': self.request.user.id if self.request.user.is_authenticated()
                            else cleaned_data.get('mixpanel_anon_id'),
                'calculator_type': 'Amazon',
                'event_type': 'Amazon Calculator Run',
                'amazonItemUrl': cleaned_data['product_url'],
                'toCountry': cleaned_data['country'].name,
                'postcode': cleaned_data.get('postcode', ''),
                'city': cleaned_data.get('city', '')
            }
            mixpanel_track_calculator.apply_async(kwargs=data, queue='analytics')
            return self.shipping_methods_json_response(
                request=self.request,
                ctx=None,
                flash_messages=None,
                task_id=task.id,
                country_code=cleaned_data['country'].iso_3166_1_a2,
                status='RUNNING',
                is_valid=True)

        return super(AmazonShippingCalculatorView, self).form_valid(form)

    def form_invalid(self, form):
        if self.request.is_ajax():
            ctx = self.get_context_data(form=form)
            return self.json_response(ctx=ctx, is_valid=False)
        return super(AmazonShippingCalculatorView, self).form_invalid(form)

    def json_response(self, ctx, **kwargs):
        payload = kwargs
        calculator_html = render_to_string(
            self.calculator_form_template_name,
            RequestContext(self.request, ctx))
        payload.update({'content_html': calculator_html})
        return HttpResponse(json.dumps(payload),
                            mimetype="application/json")

    def get_success_url(self):
        return reverse('calculators:amazon')


