from django import template
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _

register = template.Library()

@register.tag
def render_order_status_label(parser, token):
    """
    Returns the html for the order status label
    """
    args = token.split_contents()
    if len(args) < 2:
        raise template.TemplateSyntaxError(
            "render_order_status_label tag requires order status")
    return OrderStatusNode(args[1])

class OrderStatusNode(template.Node):
    def __init__(self, order_status):
        self.status = template.Variable(order_status)

    def render(self, context):
        template = '<span class="label label-%(label)s">%(status)s</span>'
        status = self.status.resolve(context).lower()
        if status == 'shipped':
            result = template % {'label': 'primary', 'status': _('Shipped')}
        elif status == 'delivered':
            result = template % {'label': 'success', 'status': _('Delivered')}
        elif status == 'return to sender':
            result = template % {'label': 'warning', 'status': _('Returning to USendHome')}
        elif status == 'failure':
            result = template % {'label': 'danger', 'status': _('Shipping failure')}
        elif status == 'refunded':
            result = template % {'label': 'warning', 'status': _('Refunded')}
        elif status == 'pending clearance':
            result = template % {'label': 'warning', 'status': _('Payment in progress ')}
        else:
            result = template % {'label': 'info', 'status': _('In Process')}
        return mark_safe(result)


