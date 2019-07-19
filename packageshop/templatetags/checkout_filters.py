from django import template

register = template.Library()


@register.filter
def is_return_to_store_checkout(request):
    try:
        ret = request.session['checkout_data']['return_to_store']['is_enabled']
    except KeyError:
        ret = False
    return ret

@register.filter
def is_return_to_store_prepaid_return_label_checkout(request):
    try:
        ret = request.session['checkout_data']['return_to_store']['prepaid_checkout']
    except KeyError:
        ret = False
    return ret

@register.filter
def is_domestic_shipment(request):
    try:
        ret = request.session['checkout_data']['shipping']['is_domestic']
    except KeyError:
        ret = False
    return ret