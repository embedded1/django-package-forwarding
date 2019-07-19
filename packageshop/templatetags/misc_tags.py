from django import template
import re
register = template.Library()


@register.assignment_tag(takes_context=True)
def is_mobile(context):
    request = context['request']
    user_agent = request.META.get('HTTP_USER_AGENT', 'mobi')
    return re.search('mobi', user_agent, re.IGNORECASE)