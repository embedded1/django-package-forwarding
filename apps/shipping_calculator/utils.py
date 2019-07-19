from django.conf import settings
from decimal import Decimal as D
from django.utils.translation import ugettext as _

WEIGHT_MAP = {
    'IL': {
        'lbs': 70,
        'kg': 31.7515
    },
    'RU': {
        'lbs': 70,
        'kg': 31.7515
    },
}

def usps_validate_package_weight(weight, country, units):
    ret = {}
    country_iso = country.iso_3166_1_a2

    try:
        max = WEIGHT_MAP[country_iso].get(units, 'lbs')
    except KeyError:
        #unknown country let USPS validate the input
        return ret
    else:
        if weight > max:
            ret['msg'] = _("Package maximum weight is: %d" % max)
            return ret

    return ret


def usps_validate_package_value(value):
    ret = {}
    min_value = D(getattr(settings, 'MIN_CONTENTS_VALUE', '1.0'))
    max_value = D(getattr(settings, 'MAX_CONTENTS_VALUE', '2499.99'))

    if value and value < min_value:
        ret['msg'] = _("Minimum content value is $%s" % min_value)
    if value and value > max_value:
        ret['msg'] = _("Maximum content value is $%s" % max_value)
    return ret
