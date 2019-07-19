from django import template
from django.utils.safestring import mark_safe
register = template.Library()

@register.filter
def create_notification_label(notification_category):
    html_tag = r'<small class="label label-%s">%s</small>'
    try:
        notification_category_lower = notification_category.lower()
    except AttributeError:
        notification_category_lower = ""

    if notification_category_lower == 'info':
        cls = "info"
    elif notification_category_lower == 'action':
        cls = "danger"
    else:
        cls = "default"

    return mark_safe(html_tag % (cls, notification_category))



