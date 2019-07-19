from oscar.apps.shipping.repository import Repository as CoreRepository
from apps.shipping import tasks
from decimal import Decimal as D
from django.core.exceptions import ObjectDoesNotExist
import logging

TWOPLACES = D('0.01')
logger = logging.getLogger('shipping repository')

class Repository(CoreRepository):
    """
    Repository class responsible for returning ShippingMethod
    objects for a given user, basket etc
    """

    def __init__(self):
        self.known_methods = []
        super(Repository, self).__init__()

    def get_shipping_methods(self, user, basket, total_value=None,
                             shipping_addr=None, package=None, **kwargs):
        """
        Launch a background task to calculate shipping methods for given basket
        """
        if shipping_addr and basket and package:
            try:
                customs_form = package.customs_form
            except ObjectDoesNotExist:
                customs_form = None

            kwargs = {
                'weight': D(package.weight).quantize(TWOPLACES),
                'length': D(package.length).quantize(TWOPLACES),
                'width': D(package.width).quantize(TWOPLACES),
                'height': D(package.height).quantize(TWOPLACES),
                'to_country': shipping_addr.country,
                'postcode': shipping_addr.postcode,
                'value': total_value,
                'customs_form': customs_form,
                'partner': package.partner,
                'battery_status': package.battery_status,
                'shipping_address': shipping_addr,
                'user': user,
                'queue': 'checkout'}
            return tasks.get_shipping_rates(**kwargs)
        return {}


    def find_by_code(self, code, basket):
        """
        Return the appropriate Method object for the given code
        """
        for klass in self.known_methods:
            if code == getattr(klass, 'code'):
                return self.prime_method(basket, klass)
        return None

    def available_shipping_methods(self, basket):
        return self.prime_methods(basket, self.known_methods)

    def get_shipping_method_by_code(self, code):
        """
        Return the appropriate Method object for the given code
        """
        for method in self.known_methods:
            if code == getattr(method, 'code'):
                return method
        return None

    def set_methods(self, methods):
        self.known_methods = methods