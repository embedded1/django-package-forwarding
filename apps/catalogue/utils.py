from apps.partner.utils import create_fee_stock_record
from django.conf import settings
from django.db.models import get_model
from django.db.models import Max
from datetime import datetime
from django.utils.translation import ugettext as _
from decimal import Decimal as D

ProductClass = get_model('catalogue', 'ProductClass')
Product = get_model('catalogue', 'Product')
ProductSpecialRequests = get_model('catalogue', 'ProductSpecialRequests')
CustomsFormItem = get_model('catalogue', 'CustomsFormItem')
Category = get_model('catalogue', 'Category')
ProductCategory = get_model('catalogue', 'ProductCategory')


def create_category(name):
    try:
        # Category names should be unique at the depth=1
        root = Category.objects.get(depth=1, name=name)
    except Category.DoesNotExist:
        root = Category.add_root(name=name)
    return root

def create_product_category(product, name):
    root = create_category(name)
    ProductCategory.objects.create(
        product=product,
        category=root)


def generate_upc():
    """
    We would like to keep package upc starting from 10000 and increment it by 1
    for every new package
    This function is called before the product has been saved to DB
    Need to return max upc and not using the last package created based on date_created attribute
    since this will not reflect the latest consolidated package where we will be using the first date
    among children
    """
    try:
        p = Product.objects.filter(product_class__name='package').aggregate(Max('upc'))
        max_upc = p['upc__max']
        new_upc = int(max_upc) + 1
        return str(new_upc)
    except (Product.DoesNotExist, TypeError):
        return '10000'


def create_fee(upc, title, package, charge, status, category_name='fee'):
    try:
        special_requests_fee_product = package.variants.get(upc=upc)
    except Product.DoesNotExist:
        product_class, _ = ProductClass.objects.get_or_create(name='fee')
        special_requests_fee_product = Product(upc=upc, status=status)
        special_requests_fee_product.title = title
        special_requests_fee_product.product_class = product_class
        special_requests_fee_product.owner = package.owner
        special_requests_fee_product.parent = package
        special_requests_fee_product.save()
        #create product category
        create_product_category(special_requests_fee_product, category_name)
    #create / update stock record
    create_fee_stock_record(special_requests_fee_product, charge)


def create_special_requests_fees(new_special_requests, old_special_requests, package, is_predefined, charges=None):
    category_name = 'special_requests_fee' if not is_predefined else 'predefined_special_requests_fee'
    #check for filling_customs_declaration fee
    if new_special_requests.is_filling_customs_declaration and\
        new_special_requests.filling_customs_declaration_done and\
        (not old_special_requests or not old_special_requests.filling_customs_declaration_done):
        upc = settings.CUSTOMS_DECLARATION_TEMPLATE % package.upc
        title= _("Customs Declaration Paperwork")
        try:
            charge = charges['customs_paperwork']
        except (TypeError, KeyError):
            charge = D(settings.FILLING_CUSTOMS_DECLARATION_CHARGE)
        create_fee(upc, title, package, charge, 'special_requests', category_name)

    #check for express_checkout fee
    if new_special_requests.is_express_checkout and\
        new_special_requests.express_checkout_done and\
        (not old_special_requests or not old_special_requests.express_checkout_done):
        upc = settings.EXPRESS_CHECKOUT_TEMPLATE % package.upc
        title = _("Express Checkout")
        try:
            charge = charges['express_checkout']
        except (TypeError, KeyError):
            charge = D(settings.EXPRESS_CHECKOUT_CHARGE)
        create_fee(upc, title, package, charge, 'special_requests', category_name)

    #check for taking_photos fee
    if new_special_requests.is_photos_required and\
        new_special_requests.photos_done and\
        (not old_special_requests or not old_special_requests.photos_done):
        upc = settings.TAKING_PHOTOS_TEMPLATE % package.upc
        num_of_photos = new_special_requests.get_number_of_photos()
        if num_of_photos == 1:
            title = _("1 Package Content Photo")
            try:
                charge = charges['1_photo']
            except (TypeError, KeyError):
                charge = D(settings.SINGLE_PHOTO_CHARGE)
        else:
            try:
                charge = charges['3_photos']
            except (TypeError, KeyError):
                charge = D(settings.THREE_PHOTOS_CHARGE)
            title = _("%(num_of_photos)d Package Content Photos") % {'num_of_photos': num_of_photos}
        create_fee(upc, title, package, charge, 'special_requests', category_name)

    #check for repackaging fee
    if new_special_requests.is_repackaging:
        if new_special_requests.repackaging_done and\
            (not old_special_requests or not old_special_requests.repackaging_done):
            upc = settings.REPACKING_TEMPLATE % package.upc
            title = _("Repacking")
            try:
                charge = charges['repacking']
            except (TypeError, KeyError):
                charge = D(settings.REPACKING_CHARGE)
            create_fee(upc, title, package, charge, 'special_requests', category_name)
        #check for 50% repackaging fee where repackaging isn't possible
        #elif not new_special_requests.repackaging_done and not old_special_requests:
        #    upc = "repackage_%s" % package.upc
        #    title = _("Unsuccessful repacking fee")
        #    charge = settings.UNSUCCESSFUL_REPACKING_CHARGE
        #    create_fee(upc, title, package, charge, 'special_requests', category_name)

    #check for custom_requests fee
    if new_special_requests.is_custom_requests and\
        new_special_requests.custom_requests_done and\
        (not old_special_requests or not old_special_requests.custom_requests_done):
        upc = settings.CUSTOM_REQUESTS_TEMPLATE % package.upc
        title = "Customized Services"
        try:
            charge = charges['customized_services']
        except (TypeError, KeyError):
            charge = D(settings.CUSTOM_REQUESTS_CHARGE)
        create_fee(upc, title, package, charge, 'special_requests', category_name)

    #check for invoice removal fee
    if new_special_requests.is_remove_invoice and\
        new_special_requests.remove_invoice_done and\
        (not old_special_requests or not old_special_requests.remove_invoice_done):
        upc = settings.REMOVE_INVOICE_TEMPLATE % package.upc
        title = _("Invoice Removal")
        try:
            charge = charges['invoice_removal']
        except (TypeError, KeyError):
            charge = D(settings.INVOICE_REMOVE_CHARGE)
        create_fee(upc, title, package, charge, 'special_requests', category_name)

    #check for extra protection fee
    if new_special_requests.is_extra_protection and\
        new_special_requests.extra_protection_done and\
        (not old_special_requests or not old_special_requests.extra_protection_done):
        upc = settings.EXTRA_PROTECTION_TEMPLATE % package.upc
        title = _("Extra Protection")
        try:
            charge = charges['extra_protection']
        except (TypeError, KeyError):
            charge = D(settings.EXTRA_PROTECTION_CHARGE)
        create_fee(upc, title, package, charge, 'special_requests', category_name)


def populate_special_requests(profile, is_waiting_for_consolidation, is_consolidated):
        special_requests_attrs = profile.get_model_attrs(ProductSpecialRequests._meta.get_all_field_names())
        #waiting consolidation packages don't support all special requests
        #consolidated packages don't support all special requests as well
        #there we need to remove unsupported special requests
        if is_consolidated:
            excluded_special_requests = settings.CONSOLIDATED_EXCLUDED_SPECIAL_REQUESTS
        elif is_waiting_for_consolidation:
            excluded_special_requests = settings.WAITING_FOR_CONSOLIDATION_EXCLUDED_SPECIAL_REQUESTS
        else:
            excluded_special_requests = []

        for key in excluded_special_requests:
                special_requests_attrs.pop(key)

        return ProductSpecialRequests(**special_requests_attrs)

def process_consolidated_package_predefined_special_request(package):
    #create special requests model based on user predefined special requests
    now = datetime.now()
    profile = package.owner.get_profile()
    special_requests = populate_special_requests(profile, False, True)
    special_requests.package = package
    special_requests.date_created = now

    #special handling for express checkout where we need to create
    #the fee over here since we immediately mark that express checkout is done
    #since no action is required by the operations staff and we need to expedite the processing
    if special_requests.is_express_checkout:
        special_requests.express_checkout_done = True
        #only express checkout selected, need to create fee right here
        create_fee(
            settings.EXPRESS_CHECKOUT_TEMPLATE % package.upc,
            _("Express Checkout"),
            package,
            settings.EXPRESS_CHECKOUT_CHARGE,
            'special_requests',
            'predefined_special_requests_fee')
    else:
        #we need to explicitly set this value because we use this value to sort the object by it
        #otherwise the value is undefined and the sort behaves abnormal
        special_requests.express_checkout_done = False

    #save to db
    special_requests.save()

def collect_customs_form_items(src_customs_form, dst_customs_form, item_list):
    for item in src_customs_form.items.all():
        customs_form_item = CustomsFormItem(
            quantity=item.quantity,
            description=item.description,
            value=item.value,
            customs_form=dst_customs_form
        )
        item_list.append(customs_form_item)

