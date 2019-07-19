from oscar.core.loading import get_model
from django.conf import settings
from decimal import Decimal as D

ShippingEventType = get_model('order', 'ShippingEventType')
ShippingEvent = get_model('order', 'ShippingEvent')
ShippingEventQuantity = get_model('order', 'ShippingEventQuantity')

def is_eei_required(customs_form, to_country, total_value=None):
    """
    EEI document is required when item's value is greater than $2500
    and the it's am international shipment
    Canada and US are exempted
    """
    EEI_EXEMPT_COUNTRIES = ['US', 'CA']

    if to_country.iso_3166_1_a2 in EEI_EXEMPT_COUNTRIES:
        return False

    #this will be the case for the shipping calculators, where we don't have a customs form
    #inc such case we're dealing with only 1 item so its easy to test it
    if customs_form is None:
        return total_value > D(settings.CONTENTS_VALUE_EEI_REQUIRED)

    return customs_form.is_eei_required()


def add_shipping_event(order, notes, event_type_name):
    """
    Create shipping event, we store latest tracking activity for reference
    1 shipping event per shipping event type
    """
    event_type, __ = ShippingEventType.objects.get_or_create(name=event_type_name)
    shipping_event, created = ShippingEvent.objects.get_or_create(
        order=order, event_type=event_type,
        defaults={'notes': notes})
    if created:
        # We assume all lines are involved in the initial payment event
        for line in order.lines.all():
            ShippingEventQuantity.objects.create(
                event=shipping_event, line=line, quantity=line.quantity)
    else:
        shipping_event.notes = notes
        shipping_event.save()




