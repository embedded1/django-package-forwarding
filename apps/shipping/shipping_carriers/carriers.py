from apps.shipping.shipping_carriers.base import ShippingMethod
from django.conf import settings


class USPS(ShippingMethod):
    carrier = settings.EASYPOST_USPS
    display_carrier = 'USPS'
    SERVICES_MAP = {
        #domestic
        'Express': ('Express Mail', '1 - 2'),
        'Priority': ('Priority Mail', '1 - 3'),
        'ParcelSelect': ('Parcel Select', '2 - 8'),
        'StandardPost': ('Standard Post', '2 - 8'),
        'First': ('First Class', '1 - 3'),
        #international
        'ExpressMailInternational': ('Express Mail', '5 - 6'),
        'PriorityMailInternational': ('Priority Mail', '6 - 10'),
        'FirstClassPackageInternationalService': ('First Class', '14 - 20'),
        'FirstClassMailInternational': ('First Class', '14 - 20')
    }

class FedEx(ShippingMethod):
    carrier = settings.EASYPOST_FEDEX
    display_carrier = 'FedEx'
    SERVICES_MAP = {
        #international
        'INTERNATIONAL_ECONOMY': ('Economy', '2 - 5'),
        'INTERNATIONAL_PRIORITY': ('Priority', '1 - 3')
    }

class UPS(ShippingMethod):
    carrier = settings.EASYPOST_UPS
    display_carrier = 'UPS'
    SERVICES_MAP = {
        #international
        'UPSSaver': ('Express Saver', '1 - 3'),
        'Expedited': ('Expedited', '2 - 5'),
        'UPSStandard': ('Standard', '3 - 10'),
    }

class TNTExpress(ShippingMethod):
    carrier = settings.EASYPOST_TNTEXPRESS
    display_carrier = 'TNT'
    SERVICES_MAP = {
        #international
        'EconomyExpress': ('Economy', '4 - 9'),
        'GlobalExpress':  ('Express', '2 - 7'),
    }

class Aramex(ShippingMethod):
    carrier = settings.EASYPOST_ARAMEX
    display_carrier = 'Aramex'
    SERVICES_MAP = {
        #international
        'PriorityParcelExpress': ('Parcel Express', '5 - 14'),
    }

class DHL(ShippingMethod):
    carrier = settings.EASYPOST_DHL
    display_carrier = 'DHL'
    SERVICES_MAP = {
        #international
        'ExpressWorldwideNonDoc': ('Express', '1 - 3'),
    }
