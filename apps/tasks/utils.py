from django.http import HttpResponse
from django.template.loader import render_to_string
from django.template import RequestContext
from django.utils import simplejson as json
from django.conf import settings


class ShippingMethodsHandler(object):
    def collect_general_shipping_messages(self, msgs):
        for tag, gen_msg in settings.GENERAL_MESSAGES:
            msgs[tag].append(gen_msg)

    def shipping_methods_json_response(self, request, ctx, flash_messages, html_template=None, **kwargs):
        payload = kwargs
        if flash_messages:
            payload['messages'] = flash_messages.to_json()
        if ctx:
            content_html = render_to_string(
                html_template,
                RequestContext(request, ctx))
            payload.update({'content_html': content_html})

        payload.update(kwargs)
        return HttpResponse(json.dumps(payload),
                            mimetype="application/json")
