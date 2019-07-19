import six
from django import forms
from django.forms.util import flatatt
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe


class UserSelect(forms.Widget):
    is_multiple = False
    style = 'width: 95%'
    css = 'select2'

    def format_value(self, value):
        return six.text_type(value or '')

    def value_from_datadict(self, data, files, name):
        value = data.get(name, None)
        if value is None:
            return value
        else:
            return six.text_type(value)

    def render(self, name, value, attrs=None, choices=()):
        attrs = self.build_attrs(attrs, **{
            'type': 'hidden',
            'class': self.css,
            'style': self.style,
            'name': name,
            'data-ajax-url': reverse('dashboard:user-lookup'),
            'data-multiple': 'multiple' if self.is_multiple else '',
            'value': self.format_value(value),
            'data-required': 'required' if self.is_required else '',
        })
        return mark_safe(u'<input %s>' % flatatt(attrs))
