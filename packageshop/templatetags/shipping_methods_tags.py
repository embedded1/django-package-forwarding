from django import template
from django.conf import settings
from django.utils.safestring import mark_safe
register = template.Library()


@register.tag
def render_shipping_method_name(parser, token):
    """
    Returns the html for the shipping method name including line break when needed
    """
    args = token.split_contents()
    if len(args) < 3:
        raise template.TemplateSyntaxError(
            "render_shipping_method_name tag requires a shipping method name and carrier")
    return ShippingMethodNameNode(args[1], args[2])


class ShippingMethodNameNode(template.Node):
    def __init__(self, method_name, carrier):
        self.method_name = template.Variable(method_name)
        self.carrier = template.Variable(carrier)

    def render(self, context):
        carrier = self.carrier.resolve(context)
        method_name = self.method_name.resolve(context)
        result = method_name
        if carrier == settings.EASYPOST_USPS:
            before, separator, after = method_name.partition('.')
            if after:
                result = "%s%s <br/>%s" % (before, separator, after)
        return mark_safe(result)


@register.tag
def render_shipping_method_logo(parser, token):
    """
    Returns the html for the shipping method name including line break when needed
    """
    args = token.split_contents()
    if len(args) < 2:
        raise template.TemplateSyntaxError(
            "render_shipping_method_logo tag requires carrier")
    return ShippingMethodLogoNode(args[1])


class ShippingMethodLogoNode(template.Node):
    def __init__(self, carrier):
        self.carrier = template.Variable(carrier)

    def render(self, context):
        carrier = self.carrier.resolve(context)

        result = "<img class=\"img-responsive\" src=\"%(static_url)s/usendhome/images/carriers/%(carrier_name)s.png\"" \
                 " alt=\"%(carrier_name)s\"/>" % {'carrier_name': carrier, 'static_url': settings.STATIC_URL}
        return mark_safe(result)

@register.assignment_tag()
def render_shipping_method_tracking_url(carrier, tracking_number):
    result = "%(url)s%(tracking)s%(extra)s"
    if carrier == settings.EASYPOST_USPS:
        result = result % {
            'url': "https://tools.usps.com/go/TrackConfirmAction.action?tRef=fullpage&tLc=1&text28777=&tLabels=",
            'tracking': tracking_number,
            'extra': ""
        }
    elif carrier == settings.EASYPOST_FEDEX:
        result = result % {
            'url': "https://www.fedex.com/apps/fedextrack/?action=track&trackingnumber=",
            'tracking': tracking_number,
            'extra': "&cntry_code=us"
        }
    elif carrier == settings.EASYPOST_TNTEXPRESS:
        result = result % {
            'url': "http://www.tnt.com/webtracker/tracking.do?navigation=1&searchType=CON&respLang=en&genericSiteIdent=.&cons=",
            'tracking': tracking_number,
            'extra': ""
        }
    elif carrier == settings.EASYPOST_UPS:
        result = result % {
            'url': "http://wwwapps.ups.com/WebTracking/track?track=yes&trackNums=",
            'tracking': tracking_number,
            'extra': ""
        }
    elif carrier == settings.EASYPOST_ARAMEX:
        result = result % {
            'url': "https://www.aramex.com/track/results?mode=0&ShipmentNumber=",
            'tracking': tracking_number,
            'extra': ""
        }
    elif carrier == settings.EASYPOST_DHL:
        result = result % {
            'url': "http://www.dhl.com/en/express/tracking.shtml?AWB=",
            'tracking': tracking_number,
            'extra': "&brand=DHL"
        }
    else:
        result = 'NO TRACKING AVAILABLE'

    return result
