from django import template
from django.utils.safestring import mark_safe
from apps.user.models import AccountStatus
from django.utils.translation import ugettext as _

register = template.Library()

@register.tag
def render_account_verification_status_label(parser, token):
    """
    Returns the html for the order status label
    """
    args = token.split_contents()
    if len(args) < 2:
        raise template.TemplateSyntaxError(
            "render_account_verification_status_label tag requires account status")
    return AccountVerificationStatusNode(args[1])

class AccountVerificationStatusNode(template.Node):
    def __init__(self, account_status):
        self.status = template.Variable(account_status)

    def render(self, context):
        template = '<span class="label label-%(label)s">%(status)s</span>'
        status = self.status.resolve(context)
        if status == AccountStatus.VERIFIED:
            result = template % {'label': 'success', 'status': _(AccountStatus.VERIFIED)}
        elif status == AccountStatus.VERIFICATION_FAILED:
            result = template % {'label': 'danger', 'status': _(AccountStatus.VERIFICATION_FAILED)}
        elif status == AccountStatus.WAITING_FOR_MORE_DOCUMENTS:
            result = template % {'label': 'info', 'status': _(AccountStatus.WAITING_FOR_MORE_DOCUMENTS)}
        else:
            result = template % {'label': 'primary', 'status': _(AccountStatus.VERIFICATION_IN_PROGRESS)}
        return mark_safe(result)

