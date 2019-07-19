from django import template
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse, NoReverseMatch
from django.contrib.sites.models import Site
from urlparse import urlparse
register = template.Library()

@register.tag
def render_email_button(parser, token):
    """
    Returns the html for the order status label
    """
    args = token.split_contents()
    if len(args) < 3:
        raise template.TemplateSyntaxError(
            "render_email_button tag requires url and text")
    btn_type = 'btn-default' if len(args) == 3 else args[3]
    return EmailButtonNode(args[1], args[2], btn_type)

class EmailButtonNode(template.Node):
    def __init__(self, url, text, type):
        self.url = template.Variable(url)
        self.text = template.Variable(text)
        self.type = template.Variable(type)

    def render(self, context):
        url = self.url.resolve(context)
        try:
            url = reverse(url)
        except NoReverseMatch:
            pass

        try:
            type = self.type.resolve(context)
        except:
            type = 'btn-default'

        if type == 'btn-large':
            style = 'style="display: inline-block;background: #337ab7;border-radius: 60px !important;' \
                    'padding: 30px;color: white;text-decoration: none;border-radius: 3px;' \
                    'margin: 10px 0;width: 400px;font-size: 24px;text-align: center;' \
                    'font-weight: 600;"'
        else:
            style = 'style="display:inline-block;background:#337ab7;padding:10px 15px;' \
                    'color:white;text-decoration:none;border-radius:3px;margin:10px 0;"'
        template = '<a href="https://%(domain)s%(url)s"' \
                   ' %(style)s>%(text)s</a>'

        url_parsed = urlparse(url)
        cta_url = url_parsed.path
        if url_parsed.query:
            cta_url += "?%s" % url_parsed.query

        result = template % {
            'domain': url_parsed.netloc if url_parsed and url_parsed.netloc else Site.objects.get_current().domain,
            'url': cta_url,
            'text': _(self.text.resolve(context)),
            'style': style
        }
        return mark_safe(result)


