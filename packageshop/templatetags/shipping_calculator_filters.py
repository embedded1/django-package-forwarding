from django.template import Library
import math

register = Library()

@register.filter
def pounds(weight):
    """
    Finds the weight of a cart item, taking into consideration the quantity in
    the order.
    """
    return int(weight)

@register.filter
def ounces(weight):
    fract = weight - pounds(weight)
    return int(math.ceil(fract * 16))

