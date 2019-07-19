from decimal import ROUND_UP, Decimal as D
from ..exceptions import (
    ShippingRevenueDoesNotExist,
    ShippingInsuranceRevenueDoesNotExist,
    ShippingMethodDoesNotExist,
    NegativeRevenue
)
from apps.address import utils
import logging
import copy

logger = logging.getLogger("management_commands")
TWOPLACES = D('0.01')

class ShippingMethod(object):
    name = None
    SERVICES_MAP= {}
    surcharges = []
    ship_charge_incl_revenue = None
    ins_charge_incl_revenue = D('0.0')
    country_code = None
    carrier = ''
    display_carrier = carrier
    envelope = False
    is_tax_known = True #To support Oscar's core
    contents_value = D('0.0')
    delivery_days = '1 - 21'
    max_delivery_days = 21

    def __init__(self, ship_charge_excl_revenue, service_code,
                 country_code, contents_value, **kwargs):
        super(ShippingMethod, self).__init__()
        self.ship_charge_excl_revenue = ship_charge_excl_revenue
        self.code = service_code
        self.country_code = country_code
        self.contents_value = contents_value
        self.ins_charge_excl_revenue = kwargs.get('insurance_charge', D('0.0'))
        try:
            self.name = self.SERVICES_MAP[self.code][0]
            self.delivery_days = self.SERVICES_MAP[self.code][1]
        except KeyError:
            logger.info("Found new EasyPost %s service: %s" % (self.display_carrier, self.code))
            raise ShippingMethodDoesNotExist

    def __unicode__(self):
        return unicode(self.name)

    def __iter__(self):
        return iter([self])

    def next(self):
        raise StopIteration

    #To support oscar's core, include tax means final rate
    #including any surcharges
    @property
    def charge_incl_tax(self):
        return self.shipping_method_cost()

    #To support oscar's core, exclude tax means EasyPost rate + surcharges (if any)
    @property
    def charge_excl_tax(self):
        return self.ship_charge_excl_revenue

    @property
    def shipping_revenue(self):
        if self.ship_charge_incl_revenue <= self.ship_charge_excl_revenue:
            raise NegativeRevenue()

        if self.ship_charge_incl_revenue is None:
            raise ShippingRevenueDoesNotExist()

        return self.ship_charge_incl_revenue - self.ship_charge_excl_revenue

    @property
    def shipping_ins_revenue(self):
        if not self.free_insurance:
            if self.ins_charge_incl_revenue <= self.ins_charge_excl_revenue:
                raise NegativeRevenue()

        if self.ins_charge_incl_revenue is None:
            raise ShippingInsuranceRevenueDoesNotExist()

        return self.ins_charge_incl_revenue - self.ins_charge_excl_revenue

    @property
    def insurance_available(self):
        return self.ins_charge_excl_revenue is not None and \
               self.ins_charge_excl_revenue > 0

    @property
    def free_insurance(self):
        return self.ins_charge_incl_revenue == 0

    @property
    def max_delivery_days(self):
        """
        We return the average of the delivery time range
        """
        days_range = self.delivery_days.split('-')
        return sum(int(day) for day in days_range) / 2

    @property
    def carrier_with_name(self):
        return "%s %s" % (self.display_carrier, self.name)

    def is_envelope(self):
        return self.envelope

    def is_domestic(self):
        return utils.is_domestic_delivery(self.country_code)

    def set_basket(self, basket):
        #no need to save basket
        #it raises cache set problems
        pass

    def get_key_by_revenue(self, revenue):
        if revenue >= 100:
            return 'xl'
        if 60 <= revenue < 100:
            return 'lg'
        if 40 <= revenue < 60:
            return 'med'
        return 'sm'

    def apply_shipping_revenues(self, shipping_revenue, min_revenue, max_revenues):
        revenue = self.ship_charge_excl_revenue * shipping_revenue
        #enforce min revenue
        if revenue < min_revenue:
            revenue = min_revenue

        #enforce max revenue
        key = self.get_key_by_revenue(revenue)
        max_revenue = max_revenues[key]
        if revenue > max_revenue:
            revenue = max_revenue

        self.ship_charge_incl_revenue = self.ship_charge_excl_revenue + revenue
        self.ship_charge_incl_revenue.quantize(TWOPLACES, rounding=ROUND_UP)

    def apply_shipping_insurance_revenues(self, insurance_revenue):
        revenue = self.ins_charge_excl_revenue * insurance_revenue
        self.ins_charge_incl_revenue = self.ins_charge_excl_revenue + revenue
        self.ins_charge_incl_revenue.quantize(TWOPLACES, rounding=ROUND_UP)


    def shipping_method_cost(self):
        """
        Shipping method cost is calculated as follows:
        1 - get rate from EasyPost (it contains surcharges)
        2 - now calculate the margin and add it to 1
        3 - we have the shipping method cost we show to customers
        """
        return self.ship_charge_incl_revenue

    def shipping_insurance_cost(self):
        return self.ins_charge_incl_revenue

    def shipping_insurance_base_rate(self):
        return self.ins_charge_excl_revenue

    def set_free_insurance(self):
        self.ins_charge_excl_revenue = \
        self.ins_charge_incl_revenue = D('0.0')

    def add_surcharges(self, surcharges):
        self.surcharges = copy.deepcopy(surcharges)

    def surcharges_cost(self):
        return D(sum(amount for desc, amount in self.surcharges))

    def surcharges_description(self):
        return ", ".join(desc for desc, amount in self.surcharges)

    def surcharges_description_and_cost(self):
        return ", ".join("(%s, %s)" % (desc, amount) for desc, amount in self.surcharges)

    def partner_postage_cost(self):
        """
        Partner pays the postage of the express carriers services and maybe of USPS
        The postage payment consists of base rate + surcharges
        """
        return self.ship_charge_excl_revenue