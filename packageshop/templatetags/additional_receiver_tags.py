from django import template
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from apps.catalogue.models import AdditionalPackageReceiver
register = template.Library()

@register.tag
def render_receiver_status(parser, token):
    """
    Returns the html for the order status label
    """
    args = token.split_contents()
    if len(args) < 2:
        raise template.TemplateSyntaxError(
            "render_receiver_status tag requires status")
    return AdditionalReceiverStatusNode(args[1])

class AdditionalReceiverStatusNode(template.Node):
    def __init__(self, verification_status):
        self.status = template.Variable(verification_status)

    def render(self, context):
        template = '<span class="label label-%(label)s">%(status)s</span>'
        status = self.status.resolve(context)
        if status == AdditionalPackageReceiver.VERIFIED:
            result = template % {'label': 'success', 'status': _(AdditionalPackageReceiver.VERIFIED)}
        elif status == AdditionalPackageReceiver.VERIFICATION_FAILED:
            result = template % {'label': 'danger', 'status': _(AdditionalPackageReceiver.VERIFICATION_FAILED)}
        elif status == AdditionalPackageReceiver.UNVERIFIED:
            result = template % {'label': 'info', 'status': _(AdditionalPackageReceiver.UNVERIFIED)}
        elif status == AdditionalPackageReceiver.WAITING_FOR_MORE_DOCUMENTS:
            result = template % {'label': 'warning', 'status': _(AdditionalPackageReceiver.WAITING_FOR_MORE_DOCUMENTS)}
        else:
            result = template % {'label': 'primary', 'status': _(AdditionalPackageReceiver.VERIFICATION_IN_PROGRESS)}
        return mark_safe(result)



