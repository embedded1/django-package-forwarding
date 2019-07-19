from django.template import Library

register = Library()

@register.filter
def title_if_not_upper(val):
    return val.title() if not val.isupper() else val
