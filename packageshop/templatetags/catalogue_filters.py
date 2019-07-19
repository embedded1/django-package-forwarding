from django.template import Library
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _

register = Library()

@register.filter
def collect_all_images(product):
    #first collect the packaging images and then the content images
    all_images = list(product.packaging_images.all()) + list(product.images.all())
    #collect combined packages content images as well (if any)
    for combine_product in product.combined_products.all():
        all_images.extend(combine_product.images.all())
    return all_images


@register.filter
def create_condition_label(product_condition):
    html_tag = r'<span class="label label-%s">%s</span>'
    product_condition_lower = product_condition.lower()

    if product_condition_lower == "perfect":
        cls = "success"
    elif product_condition_lower == "slightly damaged":
        cls = "warning"
    else:
        cls = "danger"

    return mark_safe(html_tag % (cls, product_condition))


@register.filter
def create_storage_label(days_left):
    html_tag = r'<span class="label label-%s">%s</span>'
    storage_msg = _("%d days left") % days_left

    if days_left > 3:
        cls = "success"
    elif 0 <= days_left <= 3:
        if days_left == 0:
            storage_msg = _("Last day")
        if days_left == 1:
            storage_msg = _("1 day left")
        cls = "warning"
    else:
        if days_left == -1:
            storage_msg = _("1 day over")
        else:
            storage_msg = _("%d days over") % -days_left
        cls = "danger"

    return mark_safe(html_tag % (cls, storage_msg))


