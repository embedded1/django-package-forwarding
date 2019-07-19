from decimal import Decimal as D
from ..carriers import DHL
import logging

log = logging.getLogger('management_commands')

class DHLAPICalculator(object):
    def __init__(self, to_country, postcode, weight, length, width, height, value, partner_name):
        self.country_code = to_country.iso_3166_1_a2
        self.weight = weight
        self.width = width
        self.length = length
        self.height = height
        self.value = value
        self.postcode = postcode
        self.partner_name = partner_name



    def retrieveRates(self):
        shipping_options = []

        # 1 lbs min
        if self.weight < 1:
            return shipping_options

        surcharges =  [('pickup', D('4.00'))]
        kwargs = {
            'ship_charge_excl_revenue': D('100.00'), #not needed
            'service_code': 'ExpressWorldwideNonDoc', #only 1 service supported
            'country_code': self.country_code, #not needed
            'contents_value': self.value #not needed
        }
        shipping_option = DHL(**kwargs)
        shipping_option.add_surcharges(surcharges)
        shipping_options.append(shipping_option)
        return shipping_options

    @classmethod
    def carrier_allowed(cls, weight, **kwargs):
        return weight >= 1


