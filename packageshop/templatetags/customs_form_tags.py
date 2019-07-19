from django import template
from oscar.templatetags.form_tags import FormFieldNode as CoreFormFieldNode

register = template.Library()


@register.tag
def annotate_customs_form_field(parser, token):
    """
    Set an attribute on a form field with the widget type

    This means templates can use the widget type to render things differently
    if they want to.  Django doesn't make this available by default.
    """
    args = token.split_contents()
    if len(args) < 2:
        raise template.TemplateSyntaxError(
            "annotate_form_field tag requires a form field to be passed")
    return FormFieldNode(args[1])


class FormFieldNode(CoreFormFieldNode):
    def render(self, context):
        field = self.field.resolve(context)
        if hasattr(field, 'field'):
            field.widget_type = field.field.widget.__class__.__name__
        field.is_value = "value" in field.name
        field.is_quantity = "quantity" in field.name
        field.is_desc = "desc" in field.name
        return ''