from oscar.apps.basket.abstract_models import AbstractBasket, AbstractLine
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from apps.catalogue.models import Product
from django.utils.translation import ugettext as _


class Line(AbstractLine):
    #we need to set basket position for products
    #for example: we would like to enforce that the shipping method cost will be shown first
    #and then shipping insurance cost (if any) and so on
    position = models.PositiveIntegerField(_("Position in basket"), default=0)

    class Meta:
        ordering = ["position"]


class Basket(AbstractBasket):
    #we keep reference to the package for upcoming actions
    #we must store it in db because basket is created with each request
    package = models.ForeignKey(Product, blank=True, null=True)
    INTERNATIONAL_DELIVERY, RETURN_TO_MERCHANT = (
        "International Delivery", "Return-to-Merchant")
    TYPE_CHOICES = (
        (INTERNATIONAL_DELIVERY, _(INTERNATIONAL_DELIVERY)),
        (RETURN_TO_MERCHANT, _("RETURN_TO_MERCHANT")),
    )
    type = models.CharField(
        _("Checkout Type"), max_length=128, default=INTERNATIONAL_DELIVERY, choices=TYPE_CHOICES)

    def get_package(self):
        #check if we got the package
        if self.package:
            return self.package

        #scan basket lines and find the package
        all_lines = self.all_lines()
        for line in all_lines:
            parent = line.product.parent
            if parent:
                self.package = parent
                self.save()
                return parent

        return None

    def _get_shipping_method(self):
        for line in self.all_lines():
            if line.product.product_class.name == 'shipping method':
                return line.product
        return None

    def get_selected_shipping_method_name(self):
        shipping_method = self._get_shipping_method()
        return shipping_method.title if shipping_method else None


    def remove_product_line(self, product):
        """
        Remove line of a specific product
        """
        stock_info = self.strategy.fetch_for_product(product)
        ref = self._create_line_reference(product, stock_info.stockrecord, None)
        try:
            line = self.lines.get(line_reference=ref)
            #delete this line for DB
            line.delete()
            self.reset_offer_applications()
        except ObjectDoesNotExist:
            pass

    def get_product_line(self, product):
        """
        Return a line of a specific product
        """
        stock_info = self.strategy.fetch_for_product(product)
        ref = self._create_line_reference(product, stock_info.stockrecord, None)
        try:
            line = self.lines.filter(line_reference=ref)
            return line
        except ObjectDoesNotExist:
            return None

    def add_product(self, product, quantity=1, options=None, position=None):
        """
        Add a product to the basket

        'stock_info' is the price and availability data returned from
        a partner strategy class.

        The 'options' list should contains dicts with keys 'option' and 'value'
        which link the relevant product.Option model and string value
        respectively.
        """
        if options is None:
            options = []
        if not self.id:
            self.save()

        # Ensure that all lines are the same currency
        price_currency = self.currency
        stock_info = self.strategy.fetch_for_product(product)
        if price_currency and stock_info.price.currency != price_currency:
            raise ValueError((
                "Basket lines must all have the same currency. Proposed "
                "line has currency %s, while basket has currency %s")
                % (stock_info.price.currency, price_currency))

        if stock_info.stockrecord is None:
            raise ValueError((
                "Basket lines must all have stock records. Strategy hasn't "
                "found any stock record for product %s") % product)

        # Line reference is used to distinguish between variations of the same
        # product (eg T-shirts with different personalisations)
        line_ref = self._create_line_reference(
            product, stock_info.stockrecord, options)

        # Determine price to store (if one exists).  It is only stored for
        # audit and sometimes caching.
        defaults = {
            'quantity': quantity,
            'price_excl_tax': stock_info.price.excl_tax,
            'price_currency': stock_info.price.currency,
            'position': position
        }
        if stock_info.price.is_tax_known:
            defaults['price_incl_tax'] = stock_info.price.incl_tax

        line, created = self.lines.get_or_create(
            line_reference=line_ref,
            product=product,
            stockrecord=stock_info.stockrecord,
            defaults=defaults)
        if created:
            for option_dict in options:
                line.attributes.create(option=option_dict['option'],
                                       value=option_dict['value'])
        else:
            line.quantity += quantity
            line.save()
        self.reset_offer_applications()
    add_product.alters_data = True
    add = add_product

    def add_product_if_not_exists(self, product, position, charge=None, quantity=1):
        line = self.get_product_line(product)
        if not line:
            self.add_product(product=product, position=position, quantity=quantity)
            return 'ADDED'
        else:
            if charge:
                #change the in memory object attribute to reflect this change on basket totals
                line.price_incl_tax = charge
                line.quantity = quantity
                #update DB as well
                line.update(price_incl_tax=charge, quantity=quantity)
            return 'NOT_ADDED'

    def refresh(self):
        """
        Flush all items from basket and clear vouchers
        """
        self.flush()
        self.vouchers.clear()

    def get_item_at_position(self, position):
        try:
            return self.lines.get(position=position)
        except ObjectDoesNotExist:
            return None

    def contains_line_at_position(self, position):
        return self.lines.filter(position=position).exists()


from oscar.apps.basket.models import *

