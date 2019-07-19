from decimal import Decimal as D
from django.conf import settings
from apps.address import utils
import logging

logger = logging.getLogger('revenues')

###########################
######   REVENUES    ######
###########################

class BaseRevenueApplier(object):
    SHIPPING_METHOD_REVENUES_PER_COUNTRY = {}
    shipping_method_min_revenue = D('10.0')
    shipping_method_max_revenues = {
        'sm': D('15.0'),
        'med': D('20.0'),
        'lg': D('30.0'),
        'xl': D('40.0')
    }

    def __init__(self, to_country_code, weight):
        super(BaseRevenueApplier, self).__init__()
        self.to_country_code = to_country_code
        self.weight = weight

    def get_key_by_weight(self):
        if self.weight > 8:
            return 'heavy'
        return 'light'


    def apply_shipping_method_revenue(self, method):
        key = self.get_key_by_weight()
        #Check if we have a customized revenue
        try:
            method_revenue =  self.SHIPPING_METHOD_REVENUES_PER_COUNTRY[self.to_country_code][key][method.code]
        except KeyError:
            #check if the default case has customized rate
            if method.code in self.SHIPPING_METHOD_REVENUES_PER_COUNTRY['DEFAULT'][key]:
                method_revenue = self.SHIPPING_METHOD_REVENUES_PER_COUNTRY['DEFAULT'][key][method.code]
            else:
                #fallback to default revenue for all services
                method_revenue = self.SHIPPING_METHOD_REVENUES_PER_COUNTRY['DEFAULT'][key]['*']
        method.apply_shipping_revenues(
            shipping_revenue=D(method_revenue),
            min_revenue=self.shipping_method_min_revenue,
            max_revenues=self.shipping_method_max_revenues)

        if method.insurance_available:
            self.apply_shipping_insurance_revenue(method)

    def apply_shipping_insurance_revenue(self, method):
        """
        Defaults to $0.50 for every $100 of value
        """
        method.apply_shipping_insurance_revenues(
            insurance_revenue=D('0.50'))


class ExpressCarrierRevenueApplier(BaseRevenueApplier):
    def apply_shipping_insurance_revenue(self, method):
        """
        Express carriers provide free insurance if contents value < $100
        For contents value > $100 we take extra $1 for every $100 of value
        """
        if method.contents_value < D('100.0'):
            method.set_free_insurance()
        else:
            method.apply_shipping_insurance_revenues(
                insurance_revenue=D('1.00'))

class USPSRevenueApplier(BaseRevenueApplier):
    domestic_shipping_method_min_revenue = D('15.0')
    SHIPPING_METHOD_REVENUES_PER_COUNTRY = {
        #'RU': {
        #    'ExpressMailInternational': '0.08',
        #    'PriorityMailInternational': '0.15',
        #    'FirstClassPackageInternationalService': '0.25'
        #},
        #'UA': {
        #    'ExpressMailInternational': '0.20',
        #    'PriorityMailInternational': '0.15',
        #    'FirstClassPackageInternationalService': '0.25'
        #},
        #'BR': {
        #    'ExpressMailInternational': '0.20',
        #    'PriorityMailInternational': '0.15',
        #    'FirstClassPackageInternationalService': '0.25'
        #},
        'DEFAULT': {
            'light':
            {
                'FirstClassPackageInternationalService': '0.10',
                'ExpressMailInternational': '0.10',
                'PriorityMailInternational': '0.10',
                '*': '0.10'
            },
            'heavy':
            {
                'ExpressMailInternational': '0.15',
                'PriorityMailInternational': '0.15',
                '*': '0.15'
            }
        }
    }

    def apply_shipping_method_revenue(self, method):
        """
        for domestic shipments we support only the USPS and we have different
        shipping method min revenue value
        """
        if utils.is_domestic_delivery(self.to_country_code):
            self.shipping_method_min_revenue = self.domestic_shipping_method_min_revenue
        return super(USPSRevenueApplier, self).apply_shipping_method_revenue(method)



class FedExRevenueApplier(ExpressCarrierRevenueApplier):
    SHIPPING_METHOD_REVENUES_PER_COUNTRY = {
        'DEFAULT': {
            'light':
            {
                'INTERNATIONAL_ECONOMY': '0.10',
                'INTERNATIONAL_PRIORITY': '0.10',
                '*': '0.10'
            },
            'heavy':
            {
                'INTERNATIONAL_ECONOMY': '0.15',
                'INTERNATIONAL_PRIORITY': '0.15',
                '*': '0.15'
            },
        }
    }

class TNTExpressRevenueApplier(ExpressCarrierRevenueApplier):
    SHIPPING_METHOD_REVENUES_PER_COUNTRY = {
        #'UA': {
        #    'EconomyExpress': '0.15',
        #    'GlobalExpress': '0.10',
        #},
        'DEFAULT': {
            'light':
            {
                'EconomyExpress': '0.15',
                'GlobalExpress': '0.15',
                '*': '0.15'
            },
            'heavy':
            {
                'EconomyExpress': '0.20',
                'GlobalExpress': '0.20',
                '*': '0.20'
            },
        }
    }

class UPSRevenueApplier(ExpressCarrierRevenueApplier):
    SHIPPING_METHOD_REVENUES_PER_COUNTRY = {
        'DEFAULT': {
            'light':
            {
                'UPSSaver': '0.10',
                'Expedited': '0.10',
                '*': '0.10'
            },
            'heavy':
            {
                'UPSSaver': '0.15',
                'Expedited': '0.15',
                '*': '0.15'
            },
        }
    }

class AramexRevenueApplier(BaseRevenueApplier):
    SHIPPING_METHOD_REVENUES_PER_COUNTRY = {
        'DEFAULT': {
            'light':
            {
                '*': '0.10'
            },
            'heavy':
            {
                '*': '0.15'
            },
        }
    }

class DHLRevenueApplier(BaseRevenueApplier):
    SHIPPING_METHOD_REVENUES_PER_COUNTRY = {
        'DEFAULT': {
            'light':
            {
                '*': '0.10'
            },
            'heavy':
            {
                '*': '0.15'
            },
        }
    }


def apply_revenues(methods, to_country, weight):
    CARRIER_REVENUES_MAP = {
        settings.EASYPOST_USPS: USPSRevenueApplier,
        settings.EASYPOST_FEDEX: FedExRevenueApplier,
        settings.EASYPOST_TNTEXPRESS: TNTExpressRevenueApplier,
        settings.EASYPOST_UPS: UPSRevenueApplier,
        settings.EASYPOST_ARAMEX: AramexRevenueApplier,
        settings.EASYPOST_DHL: DHLRevenueApplier,
    }

    for method in methods:
        carrier = method.carrier
        try:
            CARRIER_REVENUES_MAP[carrier](to_country.iso_3166_1_a2, weight)\
                .apply_shipping_method_revenue(method)
        except KeyError:
            logger.critical("Carrier %s not found in CARRIER_REVENUES_MAP" % carrier)








