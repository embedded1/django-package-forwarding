from django import template
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
register = template.Library()


@register.tag
def render_notification_count(parser, token):
    """
    Returns the html for the shipping method name including line break when needed
    """
    args = token.split_contents()
    if len(args) < 3:
        raise template.TemplateSyntaxError(
            "render_notification_count tag requires a current page and notifications count")
    return notificationCountNode(args[1], args[2])


class notificationCountNode(template.Node):
    def __init__(self, current_page, notifications_count):
        #we need 0 based index
        self.current_page = template.Variable(current_page)
        self.notifications_count = template.Variable(notifications_count)

    def render(self, context):
        current_page = self.current_page.resolve(context)
        notifications_count = self.notifications_count.resolve(context)
        end = current_page * 20 if current_page * 20 < notifications_count else notifications_count
        template = _("%(start)d-%(end)d of %(total)d") % {
            'start': ((current_page-1) * 20) + 1,
            'end': end,
            'total': notifications_count
        }
        return mark_safe(template)

