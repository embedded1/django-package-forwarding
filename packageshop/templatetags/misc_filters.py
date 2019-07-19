from django.template import Library

register = Library()

@register.filter
def make_range(used, total):
    if total < used:
        return range(used-total)
    return range(total-used)

@register.filter
def dec(a, b):
    return a - b

