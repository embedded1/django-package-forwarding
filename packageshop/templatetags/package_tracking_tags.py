from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.tag
def render_package_tracking_url(parser, token):
    """
    Returns the html for the order status label
    """
    args = token.split_contents()
    if len(args) < 4:
        raise template.TemplateSyntaxError(
            "render_package_tracking_url tag requires tracking number, carrier and is_html")
    return PackageTrackingUrlNode(args[1], args[2], args[3])

class PackageTrackingUrlNode(template.Node):
    def __init__(self, tracking_number, carrier, is_html):
        self.tracking_number = template.Variable(tracking_number)
        self.carrier = template.Variable(carrier)
        self.is_html = template.Variable(is_html)

    def render(self, context):
        tracking = self.tracking_number.resolve(context)
        carrier = self.carrier.resolve(context)
        is_html = self.is_html.resolve(context)

        if is_html:
            template = '<a href="%(url)s=%(tracking)s" target="_blank">%(url)s=%(tracking)s</a>'
        else:
            template = '%(url)s=%(tracking)s'

        if carrier == 'USPS':
            result = template % {
                'url': 'https://tools.usps.com/go/TrackConfirmAction.action?tRef=fullpage&tLc=1&text28777=&tLabels',
                'tracking': tracking}
        else:
            result = template % {'url': 'N/A', 'tracking': 'N/A'}
        return mark_safe(result)



