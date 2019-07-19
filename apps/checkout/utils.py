from oscar.apps.checkout.utils import CheckoutSessionData as CoreCheckoutSessionData
from django.conf import settings
from decimal import Decimal as D
from django.core.cache import cache
from apps.catalogue.models import Product
from oscar.apps.partner.models import Partner, StockRecord
from oscar.apps.shipping import methods
from apps.catalogue.models import ProductClass
import logging

logger = logging.getLogger("management_commands")

def create_fee_and_add_to_basket(title, charge, package, basket, prefix,
                                 position, product_class_name='fee',
                                 attrs=None, quantity=1, category=None, cost_price=None):

    upc = prefix % package.upc
    product_class, _ = ProductClass.objects.get_or_create(name=product_class_name)
    created = False
    try:
        product = package.variants.get(upc=upc)
    except Product.DoesNotExist:
        product = Product(upc=upc, owner=basket.owner,
                          product_class=product_class,
                          status='dynamic_fees', parent=package)
        created = True

    # Attributes
    if attrs:
        for attr in attrs:
            setattr(product.attr, attr['code'], attr['value'])

    product.title = title
    product.save()

    if created and category:
        from apps.catalogue.utils import create_product_category
        #create product category for discounts
        create_product_category(product, category)

    # STOCK RECORD
    partner, _ = Partner.objects.get_or_create(name='operations')
    updated_values = {
        'price_excl_tax': D(charge),
        'cost_price': cost_price
    }
    stock_record_qs = StockRecord.objects.filter(product=product, partner=partner)
    if not stock_record_qs:
        updated_values.update({
            'product': product, 'partner': partner,
            'partner_sku': product.upc, 'num_in_stock': None
        })
        StockRecord.objects.create(**updated_values)
    else:
        stock_record_qs.update(**updated_values)

    #update line price if product was already added to basket
    #add product to basket if it does not exist
    basket.add_product_if_not_exists(product=product,
                                     position=position,
                                     charge=charge,
                                     quantity=quantity)


class CheckoutSessionData(CoreCheckoutSessionData):
    def turn_on_package_checkout(self):
        self._unset('package_checkout', 'is_enabled')
        self._set('package_checkout', 'is_enabled', True)

    def turn_off_package_checkout(self):
        self._flush_namespace('package_checkout')

    def is_package_checkout_enabled(self):
        return self._get('package_checkout', 'is_enabled')

    def turn_on_return_to_store_checkout(self):
        self._unset('return_to_store', 'is_enabled')
        self._set('return_to_store', 'is_enabled', True)

    def is_return_to_store_enabled(self):
        return self._get('return_to_store', 'is_enabled', False)

    def set_return_to_store_content_value(self, value):
        self._unset('return_to_store', 'content_value')
        self._set('return_to_store', 'content_value', value)

    def del_return_to_store_content_value(self):
        self._unset('return_to_store', 'content_value')

    def turn_on_return_to_store_prepaid_checkout(self):
        self._unset('return_to_store', 'prepaid_checkout')
        self._set('return_to_store', 'prepaid_checkout', True)

    def set_shipping_label_id(self, shipping_label_id):
        self._unset('return_to_store', 'shipping_label_id')
        self._set('return_to_store', 'shipping_label_id', shipping_label_id)

    def get_shipping_label_id(self):
        return self._get('return_to_store', 'shipping_label_id', None)

    def turn_off_return_to_store_prepaid_checkout(self):
        self._unset('return_to_store', 'prepaid_checkout')

    def is_return_to_store_prepaid_enabled(self):
        return self._get('return_to_store', 'prepaid_checkout', False)

    def return_to_store_content_value(self):
        return_to_store_enabled = self.is_return_to_store_enabled()
        if return_to_store_enabled:
            return self._get('return_to_store', 'content_value')
        return None

    def reset_return_to_store(self):
        self._flush_namespace('return_to_store')

    def get_customs_form_key(self, key):
        return "%s_%s" % ('customs_form_fields', key)

    def is_customs_form_set(self, key):
        return self.new_customs_form_fields(key)

    def store_customs_form_fields(self, key, custom_fields):
        """
        write new custom declaration details to cache
        """
        #save repository in cache for 60 min as default
        timeout = getattr(settings, 'CUSTOMS_FORM_FIELDS_CACHE_TIMEOUT', 60 * 60)
        if key:
            key = self.get_customs_form_key(key)
            cache.set(key, custom_fields, timeout)

    def new_customs_form_fields(self, key):
        """
        Get shipping address fields from session
        """
        if key:
            key = self.get_customs_form_key(key)
            return cache.get(key)

        return None

    def get_shipping_repository_key(self, key):
        return "%s_%s" % ('shipping_repository', key)

    def reset_shipping_repository(self, key):
        if key:
            key = self.get_shipping_repository_key(key)
            cache.delete(key)

    def store_shipping_repository(self, key, repo):
        #save repository in cache for 7 days as default
        timeout = getattr(settings,
                          'SHIPPING_REPOSITORY_CACHE_TIMEOUT',
                          60 * 60 * 24 * 7)
        if key:
            key = self.get_shipping_repository_key(key)
            cache.set(key, repo, timeout)

    def available_shipping_methods(self, key, basket):
        """
        Returns the shipping methods based on the
        data stored in the session.
        """
        repository = self.get_shipping_repository(key)
        if not repository:
            return None
        return repository.available_shipping_methods(basket)

    def get_shipping_repository(self, key):
        """
        Returns the shipping repository based on the
        data stored in the session.
        """
        if key:
            key = self.get_shipping_repository_key(key)
            return cache.get(key)

        return None

    def shipping_method(self, basket=None, key=None):
        """
        Returns the shipping method model based on the
        data stored in the session.
        """
        if not basket:
            basket = self.request.basket

        if not key:
            package = basket.get_package() if basket else None
            if package:
                key = package.upc
                if self.is_return_to_store_enabled():
                    key += "_return-to-store"

        rep = self.get_shipping_repository(key)
        if rep:
            code = self._get('shipping', 'method_code')
            if code:
                return rep.find_by_code(code, basket)

        #fallback to no shipping required and catch cases where it does not allow.
        #No shipping required is only valid for return to merchant where return label provided to us
        #in all other cases we shall redirect to pending packages page with a message
        no_shipping_required =  methods.NoShippingRequired()
        return no_shipping_required

    def shipping_address_type(self, is_merchant):
        self._unset('shipping', 'is_merchant')
        self._set('shipping', 'is_merchant', is_merchant)

    def is_merchant_address(self):
        return self._get('shipping', 'is_merchant', False)

    def shipping_address_dst_type(self, is_domestic):
        self._unset('shipping', 'is_domestic')
        self._set('shipping', 'is_domestic', is_domestic)

    def is_domestic_address(self):
        return self._get('shipping', 'is_domestic', False)



