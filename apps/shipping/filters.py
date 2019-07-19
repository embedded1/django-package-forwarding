from django.conf import settings
from decimal import Decimal as D
from functools import partial
from apps.user.models import Profile
#from operator import attrgetter
from itertools import ifilter
from apps.address.utils import is_domestic_delivery
from django.core.exceptions import ObjectDoesNotExist
from apps.shipping.utils import is_eei_required
from apps.catalogue.models import Product

#def is_priority_flat_rate(method):
#    return method.carrier.upper() == 'USPS' and \
#           method.is_flat_rate() and \
#           method.code.startswith('PriorityMailInternational')

#def excluded_usps_priority_flat_rate_methods(methods):
#    """
#    We would like to display only 1 USPS priority flat rate method
#    There is no need for showing multiple flat rates for the same methods
#    currently only priority has many flat rate methods
#    """
#
#    #we start off by taking out all priority flat rate methods
#    priority_flat_rates = filter(is_priority_flat_rate, methods)
#    if len(priority_flat_rates) <= 1:
#        return []
#    sorted_priority_flat_rates = sorted(priority_flat_rates, key=attrgetter('ship_charge_incl_revenue'))
#    return sorted_priority_flat_rates[1:]

COUNTRY_SUPPORTED_CARRIERS = {'RU': [settings.EASYPOST_USPS]}
USPS_GROUND_METHOD_CODES = ['ParcelSelect', 'StandardPost']

def non_envelope_filter(shipping_method, package):
    try:
        if not package.is_envelope:
            return not shipping_method.is_envelope()
    except AttributeError:
        #We would like to show all shipping services available in the calculators
        #therefore, we return True to cancel out this feature
        pass
    return True

def non_flat_rate_filter(shipping_method, package):
    #This filter only applicable for USPS methods
    if shipping_method.carrier != settings.EASYPOST_USPS:
        return True

    try:
        if not package.flat_rate_shipping_methods_applicable():
            return not shipping_method.is_flat_rate()
    except AttributeError:
        pass
    return True

def value_filter(shipping_method, **kwargs):
    max_value_methods = [
        #'smallflatratebox',
        'FirstClassMailInternational',
        'FirstClassPackageInternationalService'
    ]

    #This filter only applicable for USPS methods
    if shipping_method.carrier != settings.EASYPOST_USPS:
        return True

    #value limitations apply only to international shipments
    if not shipping_method.is_domestic():
        if any(method == shipping_method.code for method in max_value_methods):
            if kwargs['total_value'] > D(settings.USPS_VALUE_LIMIT):
                return False
    return True

def contents_type_filter(shipping_method, package):
    """
    USPS does not allow to purchase first class label for returned goods
    Therefore, we need to filter out such method if we're dealing with such items
    Verified that EasyPost will not return such method when the content type is returned goods
    Therefore, we can count on their logic and comment out this filter
    """
    try:
        contents_type = package.customs_form.content_type
    except (AttributeError, ObjectDoesNotExist):
        contents_type = None

    if contents_type and contents_type == 'Returned Goods':
        return 'firstclass' not in shipping_method.code.lower()

    return True

def eei_required_filter(shipping_method, **kwargs):
    """
    When contents value is above $2500 we much filter out USPS methods as
    the package can't be mailed out with the USPS, EEI document required
    2 cases exist:
        1 - shipping calculators issued this call - this means that we don't have customs_form object but
            we need to work with the total_value argument
        2 - checkout process issued this call - in this case we need to work with the customs_form object
    """
    if shipping_method.carrier == settings.EASYPOST_USPS:
        customs_form = kwargs['customs_form']
        return is_eei_required(
            customs_form=customs_form,
            to_country=kwargs['to_country'],
            total_value=kwargs['total_value']) == False
    return True

def domestic_shipping_filter(shipping_method, **kwargs):
    """
    Return only USPS methods for domestic shipments
    """
    domestic_delivery = is_domestic_delivery(kwargs['to_country'].iso_3166_1_a2)
    if domestic_delivery:
        return shipping_method.carrier == settings.EASYPOST_USPS
    return True

def lithium_battery_filter(shipping_method, **kwargs):
    """
    Shipping internationally lithium batteries regulations have changed in 2017
    We have 3 cases:
    1 - No battery - all carriers accepted
    2 - Installed battery - USPS is excluded
    3 - Loose battery - only FedEx accepted
    """
    domestic_delivery = is_domestic_delivery(kwargs['to_country'].iso_3166_1_a2)
    battery_status = kwargs.get('battery_status', Product.NO_BATTERY)
    if domestic_delivery:
        #show only ground methods in case batteries exist in package
        if battery_status != Product.NO_BATTERY:
            return shipping_method.code in USPS_GROUND_METHOD_CODES
        return True

    if battery_status == Product.INSTALLED_BATTERY:
        return shipping_method.carrier != settings.EASYPOST_USPS

    if battery_status == Product.LOOSE_BATTERY:
        return False

    return True


def country_filter(shipping_method, **kwargs):
    try:
        country_code=kwargs['to_country'].iso_3166_1_a2
        return shipping_method.carrier in COUNTRY_SUPPORTED_CARRIERS[country_code]
    except Exception:
        return True

def business_user(shipping_method, **kwargs):
    """
        Filter out FedEx services for business users to avoid returns as much as possible
    """
    try:
        user = kwargs['user']
        if user:
            profile = user.get_profile()
            is_business = profile.account_type == Profile.BUSINESS
            return (not is_business) or (is_business and shipping_method.carrier != settings.EASYPOST_FEDEX)
        return True
    except Exception:
        return True


SHIPPING_METHODS_FILTERS = [
    value_filter,
    eei_required_filter,
    domestic_shipping_filter,
    lithium_battery_filter,
    country_filter,
    business_user,
    #non_envelope_filter,
    #non_flat_rate_filter,
    #contents_type_filter
]

def filter_out_shipping_methods(shipping_methods, total_value,
                                partner, customs_form,
                                battery_status, to_country, user):
    """
    We use USPS for all partners so this carrier always available at checkout
    USPS has lots of limitations we need to filter out here before we show those methods to the customer
    This is what we do for USPS methods:
    1 - flat rate methods when dealing with consolidated packages or when repacking took place
    2 - first-class mail international method for non envelope parcel
    then we need to filter out methods that don't meet USPS max value condition
    3 - We must filter out USPS when contents value is above 2499.99
    4 - at last we need to display only 1 flat rate for each method, only priority has multiple
    flat rate methods therefore we take care of it only
    Finally, we filter out methods by partner, every partner supports different set of express carriers
    """
    if not shipping_methods:
        return []
    #run methods through shipping methods filters chain
    for f in SHIPPING_METHODS_FILTERS:
        shipping_methods = ifilter(partial(
            f, total_value=total_value, customs_form=customs_form,
            to_country=to_country, battery_status=battery_status, user=user),
            shipping_methods)

    #eval
    shipping_methods = list(shipping_methods)

    #display only 1 priority international flat rate method (the cheapest one)
    #excluded_methods = excluded_usps_priority_flat_rate_methods(shipping_methods)
    #for excluded_method in excluded_methods:
    #    shipping_methods.remove(excluded_method)

    #Remove methods partner doesn't support
    partner_supported_carriers = partner.supported_carriers()
    print partner_supported_carriers
    shipping_methods = filter(lambda m: m.carrier in partner_supported_carriers, shipping_methods)

    return shipping_methods

