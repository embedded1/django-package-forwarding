from decimal import Decimal as D
from ..carriers import Aramex
import math
import logging

log = logging.getLogger('management_commands')

class AramexAPICalculator(object):
    MAX_WEIGHT = D('66.00')
    MAX_LENGTH, MAX_WIDTH, MAX_HEIGHT = D('47.00'), D('23.00'), D('23.00')
    PICKUP_RATES = {
        5: D('12.52'),
        10: D('13.78'),
        15: D('14.73'),
        20: D('15.34'),
        25: D('16.18'),
        30: D('17.64'),
        35: D('18.03'),
        40: D('19.07'),
        45: D('20.11'),
        50: D('20.56'),
        55: D('20.61'),
        60: D('21.51'),
        65: D('22.99'),
        70: D('24.00'),
        75: D('39.58'),
        80: D('43.82'),
        85: D('47.64'),
        90: D('50.90'),
        95: D('54.63'),
        100: D('59.06'),
        105: D('61.90'),
        110: D('65.34'),
        115: D('68.07'),
        120: D('71.21'),
        125: D('73.92'),
        130: D('76.82'),
        135: D('79.61'),
        140: D('82.49'),
        145: D('84.79'),
        150: D('87.09'),
    }

    SUPPORTED_COUNTRIES = [
        'SA', 'TR', 'ZA', 'SG', 'QA', 'KW', 'JO', 'KE',
        'IL', 'IN', 'EG', 'BH', 'AU', 'HK', 'OM', 'LB',
        'CY', 'AT', 'BE', 'BG', 'CZ', 'DK', 'EE', 'FI',
        'FR', 'DE', 'GH', 'GR', 'HU', 'IE', 'IT', 'LV',
        'LT', 'LU', 'MY', 'MT', 'MU', 'MA', 'NL', 'NZ',
        'NG', 'PL', 'PT', 'RO', 'RU', 'SK', 'SI', 'ES',
        'LK', 'SE', 'CH', 'TZ', 'TH', 'AE', 'GB'
    ]

    def __init__(self, to_country, postcode, weight, length, width, height, value, partner_name):
        self.country_code = to_country.iso_3166_1_a2
        self.weight = weight
        self.width = width
        self.length = length
        self.height = height
        self.value = value
        self.postcode = postcode
        self.partner_name = partner_name

    def calculate_pickup_surcharge(self):
        billable_weight = int(math.ceil(self.weight / D('5.00'))) * 5
        if billable_weight in self.PICKUP_RATES:
            pickup_rate = self.PICKUP_RATES[billable_weight]
            return [('pickup', pickup_rate)]
        return None

    def retrieveRates(self):
        shipping_options = []

        # make sure Aramex can get to the destination first
        if self.country_code not in self.SUPPORTED_COUNTRIES:
            return shipping_options

        # validate max range
        if self.length > self.MAX_LENGTH or self.height > self.MAX_HEIGHT or\
            self.width > self.MAX_WIDTH or self.weight > self.MAX_WEIGHT:
            return shipping_options

        surcharges = self.calculate_pickup_surcharge()
        kwargs = {
            'ship_charge_excl_revenue': D('100.00'), #not needed
            'service_code': 'PriorityParcelExpress', #only 1 service supported
            'country_code': self.country_code, #not needed
            'contents_value': self.value #not needed
        }
        shipping_option = Aramex(**kwargs)
        if surcharges:
            shipping_option.add_surcharges(surcharges)
        shipping_options.append(shipping_option)
        return shipping_options

    @classmethod
    def carrier_allowed(cls, city, country_code, **kwargs):
        return city and country_code in cls.SUPPORTED_COUNTRIES


