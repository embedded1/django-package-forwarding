from django import template
register = template.Library()

@register.filter(name='addcss')
def addcss(field, css):
    attrs = {}
    definition = css.split(',')

    for d in definition:
        if ':' not in d:
            attrs['class'] = d
        else:
            t, v = d.split(':')
            attrs[t] = v

    return field.as_widget(attrs=attrs)

@register.filter(name='addwrapperfieldcss')
def addwrapperfieldcss(field):
    if field.widget_type == 'Textarea':
        css_class = "textarea"
    elif field.widget_type == 'CheckboxInput':
        css_class = "checkbox"
    elif field.widget_type == 'RadioSelect':
        css_class = "radio"
    elif 'select' in field.widget_type.lower():
         css_class = "select"
    else:
        css_class = "input"

    if 'readonly' in field.field.widget.attrs:
        css_class += " state-disabled"

    return css_class
