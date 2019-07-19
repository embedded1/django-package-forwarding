from django.template import Library

register = Library()

@register.filter
def get_value(attributes, name):
    for attr in attributes:
        if name in attr.attribute.name:
            return attr._get_value()

