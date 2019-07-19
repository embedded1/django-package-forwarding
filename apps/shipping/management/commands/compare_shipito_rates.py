import json
import requests
import logging
from random import uniform, randint, choice
from decimal import Decimal as D, DivisionByZero, DivisionUndefined, InvalidOperation
from operator import itemgetter, attrgetter
from django.core.management.base import BaseCommand
from optparse import make_option
from easypost import Error
import re
from oscar.apps.address.models import Country
import time
import os
from celery.result import AsyncResult
import unicodecsv as csv
from collections import OrderedDict
from apps.shipping import tasks

logger = logging.getLogger("management_commands")

NO_SHIPPING_METHODS_STUB = [OrderedDict([
    ('name', ''),
    ('ship_charge_incl_revenue', ''),
    ('insurance_charge', '')
])]
CSV_FILE = "shipping_compare/shipping_rates_comparison_%s_after_pricing_change.csv"
SHIPITO_CALC_URL = 'https://calculator.shipito.com/en/rates'
SHIPITO_LOCATIONS = {
   #'10': 'Tualatin OR',
   #'18': 'Torrance II CA',
   #'20': 'Hawthrone CA',
   #'23': 'Minden NV',
   '7': 'Torrance CA'
}
COUNTRIES = {
    'RU': {
        'height': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 40), 'xl': (40.1, 80)},
        'width':  {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 40), 'xl': (40.1, 80)},
        'length': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 40), 'xl': (40.1, 80)},
        'weight': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 40), 'xl': (40.1, 150)},
        'city': 'moscow',
        'postcode': '107207',
        'max_girth_plus_length': 108
    },
    'AU': {
        'height': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'width':  {'xs': (1.1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'length': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'weight': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 150)},
        'city': 'sydney',
        'postcode': '2000',
        'max_girth_plus_length': 79
    },
    'SA': {
        'height': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'width':  {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'length': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'weight': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 150)},
        'city': 'Riyadh',
        'postcode': '11564',
        'max_girth_plus_length': 79
    },
    'IN': {
        'height': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'width':  {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'length': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'weight': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 150)},
        'city': 'New Delhi',
        'postcode': '110001',
        'max_girth_plus_length': 79
    },
    'BR': {
        'height': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'width':  {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'length': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'weight': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 150)},
        'city': 'rio de janeiro',
        'postcode': '20120',
        'max_girth_plus_length': 79
    },
    'DE': {
        'height': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 60)},
        'width':  {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 60)},
        'length': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 60)},
        'weight': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 150)},
        'city': 'berlin',
        'postcode': '10405',
        'max_girth_plus_length': 108
    },
    'IL': {
        'height': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'width':  {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'length': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'weight': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 36), 'xl': (36.1, 150)},
        'city': 'tel aviv',
        'postcode': '6330522',
        'max_girth_plus_length': 79
    },
    'FR': {
        'height': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'width':  {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'length': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'weight': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 150)},
        'city': 'paris',
        'postcode': '75017',
        'max_girth_plus_length': 108
    },
    'UA': {
        'height': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'width':  {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'length': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'weight': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 150)},
        'city': 'kiev',
        'postcode': '15432',
        'max_girth_plus_length': 79
    },
    'CA': {
        'height': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 40), 'xl': (40.1, 79)},
        'width':  {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 40), 'xl': (40.1, 79)},
        'length': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 40), 'xl': (40.1, 79)},
        'weight': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 40), 'xl': (40.1, 150)},
        'city': 'toronto',
        'postcode': 'M4C1B5',
        'max_girth_plus_length': 108
    },
    'GB': {
        'height': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'width':  {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'length': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'weight': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 150)},
        'city': 'london',
        'postcode': 'WC2E9RZ',
        'max_girth_plus_length': 108
    },
    'TW': {
        'height': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'width':  {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'length': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 42), 'xl': (40.1, 80)},
        'weight': {'xs': (1, 5), 'sm':(5.1, 10), 'md': (10.1, 25), 'lg': (25.1, 36), 'xl': (36.1, 150)},
        'city': 'Taipei',
        'postcode': '10542',
        'max_girth_plus_length': 79
    }
}

def create_shipito_calc_data(height, width, length, weight, country_code,
                             location_code, value, postcode, city):
    data = {"location": location_code, "country": country_code, "city": city,
            "postalcode": postcode,
            "packages": [{"dimensions_units": "in", "weight_units": "lbs", "dimension": {
                "width": str(width), "height": str(height), "length": str(length)},
                "weight": str(weight), "value": str(value)}]
    }
    return data

def generate_package_value():
    return randint(1, 2499)

def generate_random_decimal_number(start, end):
    return D(str(round(uniform(start, end), 2)))

def get_range(country_code, prop, only_big, cat=None):
    if not cat:
        cat = choice(COUNTRIES[country_code][prop].keys())
    try:
        return COUNTRIES[country_code][prop][cat]
    except KeyError:
        cat = 'md' if only_big else 'sm'
        return COUNTRIES[country_code][prop][cat]

def generate_dimensions(country_code, only_big, cat=None):
    height_start, height_end = get_range(country_code, 'height', only_big, cat)
    gen_height = generate_random_decimal_number(start=height_start, end=height_end)
    width_start, width_end = get_range(country_code, 'width', only_big, cat)
    gen_width = generate_random_decimal_number(start=width_start, end=width_end)
    length_start, length_end = get_range(country_code, 'length', only_big, cat)
    gen_length = generate_random_decimal_number(start=length_start, end=length_end)

    return (gen_height, gen_width, gen_length)

def generate_weight(country_code, only_big, cat=None):
    weight_start, weight_end = get_range(country_code, 'weight', only_big, cat)
    return generate_random_decimal_number(start=weight_start, end=weight_end)

def calculate_girth_plus_length(height, width, length):
    """
    length is the largest dimensions
    """
    largest_dim = max(height, width, length)
    other_dims = [height, width, length]
    other_dims.remove(largest_dim)
    girth = sum(other_dims) * 2
    return girth + largest_dim


def generate_package_dimensions(country_code, iter, only_big, cat):
    max_girth_plus_length = COUNTRIES[country_code]['max_girth_plus_length']
    height, width, length = generate_dimensions(country_code, only_big, cat)
    gen_girth_plus_length = calculate_girth_plus_length(height, width, length)
    if gen_girth_plus_length > max_girth_plus_length:
        if iter < 3:
            return generate_package_dimensions(country_code, iter+1, only_big, cat)
        cat = 'md' if only_big else 'sm'
        return generate_package_dimensions(country_code, 0, only_big, cat)
    return (height, width, length)

def create_shipito_calc_headers():
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.116 Safari/537.36',
        'Referer': 'http://calculator.shipito.com/en/',
        'Origin': 'http://calculator.shipito.com',
        'Host': 'calculator.shipito.com',
        #'Cookie': 'calculator=%7B%22location%22%3A%2220%22%2C%22country%22%3A%22IN%22%2C%22city%22%3A%22New%20Delhi%22%2C%22postalcode%22%3A%22110001%22%2C%22packages%22%3A%5B%7B%22dimensions_units%22%3A%22in%22%2C%22weight_units%22%3A%22lbs%22%2C%22dimension%22%3A%7B%22width%22%3A%227.77%22%2C%22height%22%3A%227.33%22%2C%22length%22%3A%229.08%22%7D%2C%22weight%22%3A%225.75%22%2C%22value%22%3A%22212%22%7D%5D%7D; __lc.visitor_id.3392252=S1405624461.5c0388dc16; _vwo_uuid=5D197620D03C7F2CFC2D65A175C8505F; _vis_opt_test_cookie=1; _ga=GA1.2.272936179.1405624432; PHPSESSID=neol2nppifslbpsq8uuh0fjll4; __utma=194711151.272936179.1405624432.1456857272.1456911651.2; __utmc=194711151; __utmz=194711151.1456911651.2.2.utmcsr=google|utmccn=(organic)|utmcmd=organic|utmctr=(not%20provided)',
    }
    return headers


def calculate_shipito_rates(height, width, length, weight, country_code, location_code, val, postcode, city):
    shipito_calc_data = create_shipito_calc_data(height, width, length, weight,
                                                 country_code, location_code, val, postcode, city)
    shipito_calc_headers = create_shipito_calc_headers()
    response = requests.post(SHIPITO_CALC_URL, data=json.dumps(shipito_calc_data), headers=shipito_calc_headers)
    if response.status_code == requests.codes.ok:
        return response.json()
    return []

def get_usps_rates(rates):
    filtered_rates = []
    sorted_rates = sort_shipping_methods(rates, key='shippingRate', comparator=itemgetter)

    for rate in sorted_rates:
        if 'usps' in rate['name'].lower():
            filtered_rates.append(OrderedDict([
                ('name', rate['name']),
                ('ship_charge_incl_revenue', D(str(rate['shippingRate']))),
                ('insurance_charge', D(str(rate['insuranceRate'])) if rate['insurable'] else 'N/A')
            ]))
    return filtered_rates

def match_method(method_name, rates):
    for rate in rates:
        if rate['name'] == method_name:
            return rate
    return None

def match_shipito_rates(rates, usendhome_rates):
    filtered_rates = []
    matched_rates = []
    unmatched_rates = []

    #filter out methods we don't support
    for rate in rates:
        #carrier = rate['name'].split(' ')[0]
        #if carrier in ['USPS']:
        filtered_rates.append(OrderedDict([
            ('name', rate['name']),
            ('ship_charge_incl_revenue', D(str(rate['shippingRate']))),
            ('insurance_charge', D(str(rate['insuranceRate'])) if rate['insurable'] else 'N/A')
        ]))

    #align our methods with shipito methods
    for usendhome_rate in usendhome_rates:
        usendhome_method_name = usendhome_rate['name'] if isinstance(usendhome_rate, OrderedDict) else\
            usendhome_rate.carrier_with_name
        matched_method = match_method(usendhome_method_name, filtered_rates)
        if matched_method:
            #found matched method
            matched_rates.append(matched_method)
        else:
            unmatched_rates.append(usendhome_rate)

    for unmatched_rate in unmatched_rates:
        usendhome_rates.remove(unmatched_rate)

    return matched_rates

def sort_shipping_methods(methods, key, comparator):
    return sorted(methods, key=comparator(key))

def split_uppercase(string):
    return re.sub(r'([a-z])([A-Z])', r'\1 \2', string)

def write_results(package_details, shipito_usps_methods, usendhome_usps_methods, writer):
    methods_available = False
    row = package_details
    if shipito_usps_methods is not None:
        for shipito_rate, usendhome_rate in zip(shipito_usps_methods, usendhome_usps_methods):
            usendhome_name = usendhome_rate['name'] if isinstance(usendhome_rate, OrderedDict) else usendhome_rate.carrier_with_name
            try:
                is_both_rates_valid = shipito_rate['name'] != NO_SHIPPING_METHODS_STUB[0]['name'] and\
                                      usendhome_name != NO_SHIPPING_METHODS_STUB[0]['name']
            except IndexError:
                is_both_rates_valid = False

            if is_both_rates_valid:
                methods_available = True
                rate_dollar_change = shipito_rate['ship_charge_incl_revenue'] - usendhome_rate.ship_charge_excl_revenue
                rate_per_change = r"%s" % round(((rate_dollar_change / usendhome_rate.ship_charge_excl_revenue) * 100), 2)
                try:
                    ins_dollar_change = shipito_rate['insurance_charge'] - usendhome_rate.shipping_insurance_cost()
                    ins_per_change = r"%s" % round(((ins_dollar_change / shipito_rate['insurance_charge']) * 100), 2)
                #catch free insurance
                except TypeError:
                    ins_dollar_change = -usendhome_rate.shipping_insurance_cost()
                    ins_per_change = r"100"
                except (DivisionByZero, DivisionUndefined, InvalidOperation):
                    ins_dollar_change = usendhome_rate.shipping_insurance_cost()
                    ins_per_change = r"0"

                row.extend([
                    shipito_rate['name'],
                    shipito_rate['ship_charge_incl_revenue'],
                    usendhome_name,
                    usendhome_rate['ship_charge_incl_revenue'] if isinstance(usendhome_rate, OrderedDict) else usendhome_rate.ship_charge_excl_revenue,
                    rate_per_change,
                    rate_dollar_change
                ])
    else:
        for rate in usendhome_usps_methods:
            usendhome_name = rate['name'] if isinstance(rate, OrderedDict) else rate.carrier_with_name
            try:
                is_rate_valid = usendhome_name != NO_SHIPPING_METHODS_STUB[0]['name']
            except IndexError:
                is_rate_valid = False
            if is_rate_valid:
                methods_available = True
                row.extend([
                    usendhome_name,
                    rate['ship_charge_incl_revenue'] if isinstance(rate, OrderedDict) else rate.ship_charge_excl_revenue,
                    '' if isinstance(rate, OrderedDict) else rate.surcharges_description_and_cost()
                ])

    if methods_available:
        writer.writerow(row)

def write_csv_header(writer, only_usendhome):
    row = []
    if not only_usendhome:
        header = ['Shipito Location', 'Destination', 'Height',
                  'Width', 'Length', 'Weight', 'Value']
        for i in range(1,5):
            method_num = ' method %d' % i
            row.extend(['Shipito' + method_num,
                        'Shipito' + method_num +' rate',
                        'usendhome' + method_num,
                        'usendhome' + method_num +' rate',
                        'Rate percentage change',
                        'Rate dollars change'])
    else:
        header = ['Destination', 'Height',
                  'Width', 'Length', 'Weight', 'Value']
        for i in range(1,5):
            method_num = ' method %d' % i
            row.extend([method_num,
                        method_num +' rate',
                        'surcharges'])

    header += row
    writer.writerow(header)

def compare_rates(country_code, rounds, all_dst, only_big, only_usendhome, **option):
    #open csv file
    csv_file = CSV_FILE % country_code.lower()
    csv_file_exists = os.path.exists(csv_file)
    output_file = open(csv_file, "w")
    writer = csv.writer(output_file, lineterminator='\n')
    #write the header only once
    if not csv_file_exists:
        write_csv_header(writer, only_usendhome)

    #default to RU country code
    try:
        COUNTRIES[country_code]
    except KeyError:
        country_code = 'RU'

    for iter_country_code in COUNTRIES.keys():
        if all_dst or (not all_dst and country_code == iter_country_code):
            for i in range(0, rounds):
                if only_big == 1:
                    cat = choice(['lg', 'xl'])
                elif only_big == 0:
                    cat = choice(['sm', 'md', 'lg'])
                else:
                    if (i % 2) == 0:
                        cat = choice(COUNTRIES[iter_country_code]['height'].keys())
                        #we will exceed max girth + length if we only pick from the large and extra large categories
                        #for those we open up the whole range
                        if cat in ['lg', 'xl']:
                            cat = None
                    else:
                        cat = None
                height, width, length = generate_package_dimensions(iter_country_code, 0, only_big, cat)
                weight = generate_weight(iter_country_code, only_big, cat)
                value = generate_package_value()
                postcode = COUNTRIES[iter_country_code]['postcode']
                city = COUNTRIES[iter_country_code]['city']
                location_code = choice(SHIPITO_LOCATIONS.keys())

                try:
                    dst_country = Country.objects.get(iso_3166_1_a2=iter_country_code)
                except Country.DoesNotExist:
                    #fallback to Russia
                    dst_country = Country.objects.get(iso_3166_1_a2='RU')

                logger.debug("Generated package: height = %s, width = %s, length = %s, weight = %s, value = %s" % (height, width, length, weight, value))
                logger.debug("Country code: %s, location code: %s, postcode: %s, city: %s" % (iter_country_code, location_code, postcode, city))

                #calculate our rates
                kwargs = {
                    'weight': weight,
                    'length': length,
                    'width': width,
                    'height': height,
                    'to_country': dst_country,
                    'value': value,
                    'postcode': postcode
                }

                try:
                    res = tasks.get_shipping_rates(**kwargs)
                    while(isinstance(res, AsyncResult)):
                        res = res.get()
                except Error:
                    logger.debug("easypost error")
                    continue
                shipping_rates = res.pop('methods', None)
                if shipping_rates:
                    sorted_usendhome_usps_rates = sort_shipping_methods(shipping_rates,
                                                                      key='carrier',
                                                                      comparator=attrgetter)
                else:
                    sorted_usendhome_usps_rates = NO_SHIPPING_METHODS_STUB

                if not only_usendhome:
                    shipito_all_rates = calculate_shipito_rates(height, width, length, weight,
                                                                iter_country_code, location_code,
                                                                value, postcode, city)
                    available_shipito_methods = filter(lambda x: 'errorMessages' not in x.keys(), shipito_all_rates)
                    if not available_shipito_methods:
                        sorted_shipito_filtered_rates = NO_SHIPPING_METHODS_STUB
                    else:
                        sorted_shipito_filtered_rates = match_shipito_rates(available_shipito_methods, sorted_usendhome_usps_rates)

                    package_details = [SHIPITO_LOCATIONS[location_code], iter_country_code, height,
                                       width, length, weight, value]
                else:
                    sorted_shipito_filtered_rates = None
                    package_details = [iter_country_code, height,
                                       width, length, weight, value]
                write_results(package_details, sorted_shipito_filtered_rates, sorted_usendhome_usps_rates, writer)

                #sleep for 5 seconds before starting the next iteration
                time.sleep(5)
    #close csv file
    output_file.close()


class Command(BaseCommand):
    """
    Check for packages with 3 days before storage fee applied and alert the user
    have registered for an alert.
    """
    help = ("Compare shipito shipping rates to our rates")
    option_list = BaseCommand.option_list + (
        make_option('-c', '--country_code', type='str', default='RU',
            help="Destination country code"),
        make_option('-r', '--rounds', type='int', default=1,
            help="Number of packages to compare"),
        make_option('-a', '--all-dst', type='int', default=0,
            help="Get rates from all destination"),
        make_option('-o', '--only-big', type='int', default=0,
            help="Generate only big and heavy packages"),
        make_option('-u', '--only-usendhome', type='int', default=0,
            help="Get USendHome's rate only"),
    )

    def handle(self, country_code, rounds, all_dst, only_big, only_usendhome, **options):
        compare_rates(country_code, rounds, all_dst, only_big, only_usendhome)






