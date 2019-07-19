from __future__ import absolute_import
from decimal import Decimal as D
import urllib2
import gzip
from itertools import chain
#from functools import partial
import logging
import math
from packageshop.celery import app
from celery import group, chain as celery_chain
from .apis import EasyPostAPI
from . import revenues, cache, filters
from apps.address import utils
from apps.shipping.shipping_carriers.apis.usps import UspsAPICalculator
from apps.shipping.shipping_carriers.apis.Fedex import FedexAPICalculator
from apps.shipping.shipping_carriers.apis.ups import UPSAPICalculator
from apps.shipping.shipping_carriers.apis.aramex import AramexAPICalculator
from apps.shipping.shipping_carriers.apis.dhl import DHLAPICalculator
from django.conf import settings
from amazon.api import AmazonAPI
import re
from lxml import html
from apps.address.models import Country
from django.utils.translation import ugettext as _
import simplejson as json
from django.core.urlresolvers import reverse
from django.contrib import messages
from apps.partner.models import Partner
from apps.shipping.pyshipping.package import Package
from apps.shipping.pyshipping.binpack_simple import binpack
from operator import attrgetter


try:
    from cStringIO import StringIO
except ImportError:
    try:
        from StringIO import StringIO
    except ImportError:
        from io import StringIO

logger = logging.getLogger("management_commands")

amazon = AmazonAPI(
    settings.AMAZON_ACCESS_KEY,
    settings.AMAZON_SECRET_KEY,
    settings.AMAZON_ASSOC_TAG
)

if settings.DEBUG:
    easypostapi = EasyPostAPI()
    #easypostapi = EasyPostAPI(api_key=settings.EASYPOST_LIVE_API_KEY)
else:
    easypostapi = EasyPostAPI()

@app.task(soft_time_limit=30)
def _fetch_amazon_product(product_url):
    flash_messages = {
        messages.ERROR: [],
        messages.INFO: [],
        messages.WARNING: [],
    }
    amazon_product_data = {}

    amazon_regex_pattern = r"^(http|https)://www.amazon.com/([\w-]+/)?(dp|gp/product|exec/obidos/asin|gp/aw/d)/(\w+/)?(\w{10})"
    result = re.match(amazon_regex_pattern, product_url)
    if not result:
        amazon_general_error(flash_messages)
        logger.error("We could not scrape amazon product asin from url: %s" % product_url)
        return amazon_product_data, flash_messages

    asin = result.group(5)
    if not asin:
        amazon_general_error(flash_messages)
        logger.error("asin was not shown in group(4) from url: %s" % product_url)
        return amazon_product_data, flash_messages

    get_amazon_product_data(
        asin=asin, flash_messages=flash_messages,
        amazon_product_data=amazon_product_data,
        product_url=product_url)

    return amazon_product_data, flash_messages


@app.task
def collect_all_shipping_methods(methods, to_country, flash_messages, **kwargs):
    ret = {'flash_messages': flash_messages}
    if not methods:
        flash_messages[messages.INFO].append(_("No matching shipping methods found, please contact customer support."))
        ret['methods'] = []
    else:
        sorted_methods = sorted(methods, key=attrgetter('ship_charge_excl_revenue'))
        #filter out unavailable shipping methods
        filtered_methods = filters.filter_out_shipping_methods(
            shipping_methods=sorted_methods,
            total_value=kwargs['value'],
            partner=kwargs['partner'],
            customs_form=kwargs['customs_form'],
            battery_status=kwargs.get('battery_status'),
            user=kwargs.get('user'),
            to_country=to_country)
        revenues.apply_revenues(filtered_methods, to_country, kwargs['weight'])
        ret['methods'] = filtered_methods

    #collect data
    for key, value in kwargs.iteritems():
        if isinstance(value, dict):
            ret.update(value)
        else:
            ret[key] = value
    return ret

#@app.task
#def get_usps_non_flat_methods(usps_api_methods, easypost_api_methods):
#    #filter out easypost USPS methods that don't exists in the methods returned from USPS directly
#    return filter(partial(usps_filter, usps_methods=usps_api_methods), easypost_api_methods)

def add_surcharge_to_canada(method):
    if getattr(method, 'country_code', False) and method.country_code == 'CA':
        method.add_surcharges([('rate alignment', D('5.00'))])
        method.ship_charge_excl_revenue += D('5.00')


@app.task
def methods_post_processing(easypost_api_methods): #aramex_api_methods): #, fedex_api_methods, ups_api_methods #aramex_api_methods, dhl_api_methods):
    """
    Here we return all express carrier methods and we link between
    methods and surcharges
    """
    methods = []
    for method in easypost_api_methods:
        if method.carrier in (settings.EASYPOST_FEDEX, settings.EASYPOST_UPS):
            # we need to align the rates to Canada
            add_surcharge_to_canada(method)
            methods.append(method)
        elif method.carrier == settings.EASYPOST_USPS:
            methods.append(method)
        elif method.carrier == settings.EASYPOST_ARAMEX:
            # make sure Aramex can ship the package before showing it to the user
            #if aramex_api_methods:
                # pickup is free so we don't need to add surcharges at all
            methods.append(method)
        #elif method.carrier == settings.EASYPOST_ARAMEX:
        #    #pickup surcharges are not returned via Easypost, we calculate them manually
        #    #and creating a method that stores them
        #    for aramex_method in aramex_api_methods:
        #        if aramex_method.code == method.code:
        #            method.add_surcharges(aramex_method.surcharges)
        #            method.ship_charge_excl_revenue += aramex_method.surcharges_cost()
        #            methods.append(method)
        #            break
        elif method.carrier == settings.EASYPOST_DHL:
            #pickup surcharges are not returned via Easypost, we calculate them manually
            #and creating a method that stores them
            #for dhl_method in dhl_api_methods:
            #    if dhl_method.code == method.code:
                method.add_surcharges([('pickup', D('4.00'))])
                method.ship_charge_excl_revenue += D('4.00')
                methods.append(method)
        #if method.carrier == settings.EASYPOST_FEDEX:
        #    #add surcharges description and costs and make sure both rates equal
        #    for fedex_method in fedex_api_methods:
        #        if fedex_method.code == method.code:
        #            #if fedex rate is greater than easypost rate then we take the fedex rate
        #            if fedex_method.charge_excl_tax > method.charge_excl_tax:
        #                method.ship_charge_excl_revenue = fedex_method.ship_charge_excl_revenue
        #            method.add_surcharges(fedex_method.surcharges)
        #            methods.append(method)
        #            break
        #elif method.carrier == settings.EASYPOST_TNTEXPRESS:
        #    #Easypost doesn't return all of TNT surcharges and we don't use TNT API directly
        #    #to retrieve those so we will add a fixed surcharges of $30
        #    method.add_surcharges([('fixed', '30.0')])
        #    method.ship_charge_excl_revenue += D('30.0')
        #    methods.append(method)
        #elif method.carrier == settings.EASYPOST_UPS:
        #    for ups_method in ups_api_methods:
        #        if ups_method.code == method.code:
        #            #if UPS rate is greater than easypost rate then we take the UPS rate
        #            if ups_method.charge_excl_tax > method.charge_excl_tax:
        #                method.ship_charge_excl_revenue = ups_method.ship_charge_excl_revenue
        #            methods.append(method)
        #            break
    return methods


@app.task
def process_intl_shipping_methods(output, flash_messages, queue, to_country, **kwargs):
    """
    rates argument should contain the matching rates we received from USPS, FedEx, UPS and Easypost APIs
    """
    if len(output) != 1 :
        flash_messages[messages.ERROR].append(_("Something went terribly wrong, please try again shortly."))
        return {'flash_messages': flash_messages}

    #usps_api_methods = output[0]
    #easypost_api_methods = output[0]
    #fedex_api_methods = output[1]
    #ups_api_methods = output[2]
    #aramex_api_methods = output[3]
    #dhl_api_methods = output[4]

    subtasks = []
    easypost_api_methods = output[0]
    #aramex_api_methods = output[1]

    if not easypost_api_methods:
        flash_messages[messages.ERROR].append(_("Something went terribly wrong, please try again shortly."))
        return {'flash_messages': flash_messages}

    #if not fedex_api_methods:
    #    flash_messages[messages.ERROR].append(_("FedEx methods can't be retrieved at the moment."))

    #if not ups_api_methods:
    #    flash_messages[messages.ERROR].append(_("UPS methods can't be retrieved at the moment."))

    #Filter the flat rate methods so we could ask for easypost rates
    #usps_flat_methods = filter(lambda x: x.carrier == 'USPS' and x.is_flat_rate(), usps_api_methods)
    #unique_predefined_parcels = set(map(lambda x: x.code.split('-')[1], usps_flat_methods))

    #for predefined_parcel in unique_predefined_parcels:
    #    subtasks.append(calculate_flat_rate_methods.s(weight, length, width, height, value,
    #        predefined_parcel, to_country, postcode, partner, customs_form).set(queue=queue))

    #subtasks.append(get_usps_non_flat_methods.s(usps_api_methods, easypost_api_methods)
    #                .set(soft_timeout=10, queue=queue))
    subtasks.append(methods_post_processing.s(easypost_api_methods)
                    .set(soft_timeout=10, queue=queue))
    subwork = group(*subtasks) | collect_all_shipping_methods.s(to_country, flash_messages, **kwargs)\
        .set(soft_timeout=10, queue=queue)
    return subwork()


@app.task
def chrome_process_intl_shipping_methods(data, packages_data, no_data_items,
                                         flash_messages, to_country, **kwargs):
    """
    This function receives all data from external services and processes it
    The data should be handled in 2 items per result
    """
    i = 0
    j = 0
    one_package = False
    ret = [no_data_items, to_country]
    while(i < len(data)):
        if isinstance(data[i], list):
            easypost_api_methods = data[i]
        else:
            easypost_api_methods = data
            one_package = True

        #aramex_api_methods = data[i+1]

        #fedex_api_methods = data[i+1]
        #ups_api_methods = data[i+2]
        #dhl_api_methods = data[i+4]
        methods = methods_post_processing(easypost_api_methods)
        ret.append(collect_all_shipping_methods(methods=methods,
                                                flash_messages=flash_messages, **packages_data[j]))

        # break the loop if we're dealing only with 1 package as we consumed all methods already
        if one_package:
            break

        i += 2
        j += 1

    return ret


@app.task
def calculate_usps_intl_rate(weight, length, width, height, value, to_country, **kwargs):
    usps_api = UspsAPICalculator(
        to_country=to_country,
        weight=weight,
        length=length,
        height=height,
        width=width,
        value=value)

    return usps_api.retrieveShippingOptions()


@app.task
def calculate_fedex_rates(weight, length, width, height,
                          to_country, postcode, value, partner, **kwargs):
    fedex_api = FedexAPICalculator(
        to_country=to_country,
        postcode=postcode,
        weight=weight,
        length=length,
        width=width,
        height=height,
        value=value,
        partner_name=partner.name)

    return fedex_api.retrieveRates()

@app.task
def calculate_ups_rates(weight, length, width, height,
                        to_country, postcode, value, partner, **kwargs):
    ups_api = UPSAPICalculator(
        to_country=to_country,
        postcode=postcode,
        weight=weight,
        length=length,
        width=width,
        height=height,
        value=value,
        partner_name=partner.name)

    return ups_api.retrieveRates()

@app.task
def calculate_aramex_rates(weight, length, width, height,
                           to_country, postcode, value, partner, **kwargs):
    """
    We don't use Aramex's API directly but this class is responsible for adding the pickup surcharges
    """
    aramex_api = AramexAPICalculator(
        to_country=to_country,
        postcode=postcode,
        weight=weight,
        length=length,
        width=width,
        height=height,
        value=value,
        partner_name=partner.name)

    return aramex_api.retrieveRates()

@app.task
def calculate_dhl_rates(weight, length, width, height,
                        to_country, postcode, value, partner, **kwargs):
    """
    We don't use Aramex's API directly but this class is responsible for adding the pickup surcharges
    """
    dhl_api = DHLAPICalculator(
        to_country=to_country,
        postcode=postcode,
        weight=weight,
        length=length,
        width=width,
        height=height,
        value=value,
        partner_name=partner.name)

    return dhl_api.retrieveRates()

@app.task
def calculate_intl_shipping_rates(**kwargs):
    return easypostapi.calculate_intl_shipping_rates(**kwargs)

@app.task
def calculate_domestic_shipping_rates(**kwargs):
    return easypostapi.calculate_domestic_shipping_rates(**kwargs)

#@app.task
#def calculate_flat_rate_methods(weight, length, width, height, value,
#                                predefined_parcel, to_country,
#                                postcode, partner, customs_form=None, **kwargs):
#    return easypostapi.calculate_flat_rate_methods(weight, length, width, height, value,
#                                                   predefined_parcel, to_country,
#                                                   postcode, customs_form, partner)

def usps_filter(easypost_method, usps_methods):
    for usps_method in usps_methods:
        if usps_method.code == easypost_method.code:
            return True
    return False

def align_amazon_units(units):
    """
    Amazon uses needs to be aligned by dividing by 100
    """
    return map(lambda (k,v): D(v) / D('100'), units.iteritems())


def amazon_general_error(flash_messages):
    flash_messages[messages.ERROR].append(
        _("We were unable to retrieve product's dimensions from Amazon.<br/>Please contact the seller and ask for the dimensions, then"
          " use the <a href='%s'>package calculator</a>.") % reverse('calculators:package')
    )

def get_domestic_predefined_parcels(weight, length, width, height, value, **kwargs):
    return easypostapi.get_domestic_flat_methods(weight, length, width, height, value)

def create_shipping_work(input_kwargs, queue, flash_messages, **kwargs):
    tasks = []
    partner = input_kwargs.get('partner')

    if partner is None:
        input_kwargs['partner'] = get_partner()

    if utils.is_domestic_delivery(input_kwargs['to_country'].iso_3166_1_a2):
        #We only ship domestic via the USPS
        tasks.append(calculate_domestic_shipping_rates.s(**input_kwargs).set(soft_timeout=10, queue=queue))
        #domestic_predefined_parcels = get_domestic_predefined_parcels(**input_kwargs)
        #for domestic_predefined_parcel in domestic_predefined_parcels:
        #    tasks.append(calculate_flat_rate_methods.s(predefined_parcel=domestic_predefined_parcel,
        #                                               **input_kwargs).set(queue=queue))
        kwargs.update(input_kwargs)
        work = group(*tasks) | collect_all_shipping_methods.s(
            flash_messages=flash_messages, **kwargs).set(soft_timeout=10, queue=queue)
    else:
        tasks.extend([
            #calculate_usps_intl_rate.s(**input_kwargs).set(soft_timeout=10, queue=queue),
            calculate_intl_shipping_rates.s(**input_kwargs).set(soft_timeout=10, queue=queue),
            #calculate_fedex_rates.s(**input_kwargs).set(soft_timeout=10, queue=queue),
            #calculate_ups_rates.s(**input_kwargs).set(soft_timeout=10, queue=queue),
            #calculate_aramex_rates.s(**input_kwargs).set(soft_timeout=10, queue=queue),
            #calculate_dhl_rates.s(**input_kwargs).set(soft_timeout=10, queue=queue)
        ])
        work = group(*tasks) | process_intl_shipping_methods.s(flash_messages=flash_messages,
                                                               queue=queue,
                                                               to_country=input_kwargs['to_country'],
                                                               value=input_kwargs['value'],
                                                               weight=input_kwargs['weight'],
                                                               customs_form=input_kwargs['customs_form'],
                                                               partner=input_kwargs['partner'],
                                                               **kwargs).set(soft_timeout=10, queue=queue)
    return work

def create_chrome_shipping_work(input_kwargs, queue, **kwargs):
    tasks = []
    partner = input_kwargs.get('partner')

    if partner is None:
        input_kwargs['partner'] = get_partner()

    tasks.extend([
        #calculate_usps_intl_rate.s(**input_kwargs).set(soft_timeout=10, queue=queue),
        calculate_intl_shipping_rates.s(**input_kwargs).set(soft_timeout=10, queue=queue),
        #calculate_fedex_rates.s(**input_kwargs).set(soft_timeout=10, queue=queue),
        #calculate_ups_rates.s(**input_kwargs).set(soft_timeout=10, queue=queue),
        calculate_aramex_rates.s(**input_kwargs).set(soft_timeout=10, queue=queue),
        #calculate_dhl_rates.s(**input_kwargs).set(soft_timeout=10, queue=queue)
    ])

    return tasks

def get_partner():
    #look in cache
    partner = cache.get_active_partner()
    #fallback to db if we didn't find partner in cache or the partner in cache
    #is not the active partner anymore
    if partner is None or partner.name != settings.ACTIVE_PARTNER_NAME:
        partner = Partner.objects.get(name=settings.ACTIVE_PARTNER_NAME)
        #store active partner in cache for further requests
        cache.store_active_partner(partner)
    return partner

def get_shipping_rates(weight, length, width, height, value, to_country,
                       postcode=None, customs_form=None, queue='calculators',
                       partner=None, **kwargs):
    #logger.info("Calculating shipping rates for package: height: %s, width: %s, length:%s, weight: %s, "
    #             "value: %s, destination: %s" % (height, width, length, weight, value, to_country))
    flash_messages = {
        messages.ERROR: [],
        messages.INFO: [],
        messages.WARNING: [],
    }

    #we set a max value of 2499.99, return no shipping methods if value exceeds this limit
    if value > D(settings.MAX_CONTENTS_VALUE):
        flash_messages[messages.ERROR].append(_("Package content total value must not exceed $%s"
                                                % settings.MAX_CONTENTS_VALUE))
        return {'flash_messages': flash_messages}

    input_kwargs = {
        'weight': weight,
        'length': length,
        'width': width,
        'height': height,
        'value': value,
        'to_country': to_country,
        'postcode': postcode,
        'customs_form': customs_form,
        'partner': partner,
        'shipping_address': kwargs.get('shipping_address'),
        'city': kwargs.get('city')
    }
    work = create_shipping_work(input_kwargs, queue, flash_messages, **kwargs)
    return work()

def trigger_request_to_amazon(asin_numbers, **kwargs):
    retry = kwargs.get('retry', 0)
    products = []

    if retry == 3:
        exception = kwargs.get('exception', 'N/A')
        logger.error("Amazon lookup failed, error: %s", exception)
        return products

    try:
        products = amazon.lookup(ItemId=asin_numbers)
    except Exception as e:
        kwargs['retry'] = retry + 1
        kwargs['exception'] = unicode(e)
        trigger_request_to_amazon(asin_numbers, **kwargs)

    return products

def get_amazon_products_data(asin_numbers, amazon_products_data):
    products = trigger_request_to_amazon(asin_numbers)

    if not isinstance(products, list):
        products = [products]

    for product in products:
        item_info_fetched = package_info_fetched = False
        item_dimensions = align_amazon_units(product.get_attributes([
            'ItemDimensions.Width', 'ItemDimensions.Height',
            'ItemDimensions.Length', 'ItemDimensions.Weight'
        ]))
        package_dimensions = align_amazon_units(product.get_attributes([
            'PackageDimensions.Width', 'PackageDimensions.Height',
            'PackageDimensions.Length', 'PackageDimensions.Weight'
        ]))
        if len(item_dimensions) == 4 and \
             all(i > 0 for i in item_dimensions):
            item_weight = item_dimensions[3]
            item_width, item_height, item_length = (item_dimensions[0], item_dimensions[1], item_dimensions[2])
            item_info_fetched = True

        if len(package_dimensions) == 4 and \
           all(i > 0 for i in package_dimensions):
            package_weight = package_dimensions[3]
            package_width, package_height, package_length = (package_dimensions[0],
                                                             package_dimensions[1],
                                                             package_dimensions[2])
            package_info_fetched = True

        if not package_info_fetched and not item_info_fetched:
            #just save title and continue
            amazon_products_data[product.asin].update({'title': product.title})
            continue

        price_and_currency = product.price_and_currency
        if price_and_currency[0] is None:
            price_and_currency = product.list_price

        data = {
            'value': D(price_and_currency[0] if price_and_currency and
                                                price_and_currency[0] else '100.0'),
            'title': product.title,
        }

        if item_info_fetched:
            data.update({
                'weight': item_weight,
                'width': item_width,
                'height': item_height,
                'length': item_length
            })

        if package_info_fetched:
            data.update({
                'package_weight': package_weight,
                'package_width': package_width,
                'package_height': package_height,
                'package_length': package_length
            })
            if not item_info_fetched:
                data.update({
                    'weight': data['package_weight'],
                    'width': data['package_width'],
                    'height': data['package_height'],
                    'length': data['package_length']
                })

        amazon_products_data[product.asin].update(data)

def get_amazon_product_data(asin, flash_messages, amazon_product_data, product_url=None):
    product = trigger_request_to_amazon(asin)
    if product:
        price_and_currency = product.price_and_currency
        package_dimensions = align_amazon_units(product.get_attributes([
            'PackageDimensions.Width', 'PackageDimensions.Height',
            'PackageDimensions.Length', 'PackageDimensions.Weight'
        ]))
        item_dimensions = align_amazon_units(product.get_attributes([
            'ItemDimensions.Width', 'ItemDimensions.Height',
            'ItemDimensions.Length', 'ItemDimensions.Weight'
        ]))
        #print product.to_string()
        #validate that we got all info we needed
        if price_and_currency[0] is None:
            #check for list price
            price_and_currency = product.list_price
            if price_and_currency[0] is None and product_url is not None:
                #The price may be hidden - lets try one final step before giving up
                #try to fetch the price from the html
                try:
                    request = urllib2.Request(product_url, headers={"Accept-Encoding": "gzip"})
                    response = urllib2.urlopen(request)
                    if "gzip" in response.info().getheader("Content-Encoding"):
                        gzipped_file = gzip.GzipFile(fileobj=StringIO(response.read()))
                        response_text = gzipped_file.read()
                    else:
                        response_text = response.read()
                except Exception as e:
                    amazon_general_error(flash_messages)
                    logger.error("Fetching Amazon product price from html failed,"
                                 " url: %s, error: %s" % (product_url, unicode(e)))
                    return amazon_product_data, flash_messages
                doc = html.fromstring(response_text)
                price = doc.xpath('//div[@id="fbt_item_data"]')
                price_and_currency = []
                if len(price) == 1:
                    output = json.loads(price[0].text)
                    for data in output['itemData']:
                        if 'buyingPrice' in data and 'ASIN' in data and data['ASIN'] == asin:
                            price_and_currency.append(data['buyingPrice'])
                            price_and_currency.append('USD')
                if not price_and_currency:
                    amazon_general_error(flash_messages)
                    logger.info("we did not get price and currency from url: %s" % product_url)
                    return amazon_product_data, flash_messages

        #check if we got package dimensions which better reflect the shipping costs
        if len(package_dimensions) == 4 and \
           all(i > 0 for i in package_dimensions):
            weight = package_dimensions[3]
            width, height, length = (package_dimensions[0], package_dimensions[1], package_dimensions[2])
        #fallback to item dimensions and display info msg to user
        elif len(item_dimensions) == 4 and \
             all(i > 0 for i in item_dimensions):
            weight = item_dimensions[3]
            width, height, length = (item_dimensions[0], item_dimensions[1], item_dimensions[2])
            #we need to let the customer know that we calculate the shipping
            #costs based on item properties and not based on package properties
            flash_messages[messages.INFO].append(_("Shipping costs were calculated using product's"
                                          " dimensions and not by using product's packaging dimensions. Final costs may vary."))
            logger.warning("shipping costs calculated based on product properties and not based on"
                           " package properties")
        else:
            #error occurred fetching dimension
            amazon_general_error(flash_messages)
            logger.info("we did not get dimensions")
            return amazon_product_data, flash_messages

        amazon_product_data.update({
            'value': D(price_and_currency[0]),
            'weight': weight,
            'width': width,
            'length': length,
            'height': height,
            'title': product.title,
            'img': product.large_image_url,
            'purchase_url': product_url
        })
    else:
        amazon_general_error(flash_messages)
        logger.error("We could not get product/package dimension")
        return amazon_product_data, flash_messages


@app.task
def calculate_shipping_rates(output, to_country, queue='calculators',
                             partner=None, postcode=None, city=None, user=None):
    flash_messages = {
        messages.ERROR: [],
        messages.INFO: [],
        messages.WARNING: [],
    }

    if len(output) != 2:
        flash_messages[messages.ERROR].append(_("Something went terribly wrong, please try again shortly."))
        return {'flash_messages': flash_messages}

    amazon_product_data, flash_messages = output
    if not amazon_product_data:
        return {'flash_messages': flash_messages}

    if amazon_product_data['value'] >  D(settings.MAX_CONTENTS_VALUE):
        flash_messages[messages.ERROR].append(_("Item's value must not exceed $%s"
                                              % settings.MAX_CONTENTS_VALUE))
        return {'flash_messages': flash_messages}

    input_kwargs = {
        'weight': amazon_product_data['weight'],
        'length': amazon_product_data['length'],
        'width': amazon_product_data['width'],
        'height': amazon_product_data['height'],
        'value': amazon_product_data['value'],
        'to_country': to_country,
        'postcode': postcode,
        'city': city,
        'customs_form': None,
        'partner': partner
    }

    work = create_shipping_work(input_kwargs, queue, flash_messages, amazon_product_data=amazon_product_data, user=user)
    return work()

def get_shipping_rates_amazon(product_url, to_country, postcode=None, city=None, user=None):

    work = celery_chain(_fetch_amazon_product.s(product_url=product_url).set(queue='calculators'),
                        calculate_shipping_rates.s(to_country=to_country, postcode=postcode, city=city, user=user).set(
                            soft_timeout=10, queue='calculators'))
    return work()

def get_shipping_rates_chrome(items, to_country, postcode, city, include_usps):
    try:
        country = Country.objects.get(iso_3166_1_a2=to_country)
    except Country.DoesNotExist:
        #fallback to default country which is Germany
        country = Country.objects.get(iso_3166_1_a2='DE')
    work = celery_chain(
        get_amazon_items.s(items).set(queue='calculators'),
        split_items_into_bins.s(include_usps).set(queue='calculators'),
        calculate_shipping_methods_for_bins.s(to_country=country, postcode=postcode, city=city).set(queue='calculators')
    )
    return work()


@app.task
def calculate_shipping_methods_for_bins(output, to_country, postcode, city):
    def get_total_value(packages):
        total_value = D('0.0')
        for package in packages:
            total_value += package.value
        return total_value

    def get_bin_weight(bin):
        """
        bin weight = the sum of all item's weight inside the bin + bin weight
        """
        bin_packages = bin['packages']
        total_weight = bin['bin'].weight
        for package in bin_packages:
            total_weight += package.weight
        return total_weight

    subtasks = []
    packages_data = []
    queue = 'calculators'
    bins, rest, no_data_items = output
    flash_messages = {
        messages.ERROR: [],
        messages.INFO: [],
        messages.WARNING: [],
    }

    for bin in bins:
        input_kwargs = {
            'length': D(bin['bin'].length),
            'width': D(bin['bin'].width),
            'height': D(bin['bin'].height),
            'weight': get_bin_weight(bin),
            'value': get_total_value(bin['packages']),
            'customs_form': None,
            'to_country': to_country,
            'postcode': postcode,
            'city': city,
        }
        subtasks += create_chrome_shipping_work(input_kwargs, queue, bin=bin)
        #add bin packages
        input_kwargs['packages'] = bin['packages']
        packages_data.append(input_kwargs)

    #rest packages are too big, we must calculate shipping methods separately
    for package in rest:
        input_kwargs = {
            'length': D(package.length),
            'width': D(package.width),
            'height': D(package.height),
            'weight': D(package.weight),
            'value': D(package.value),
            'customs_form': None,
            'to_country': to_country,
            'postcode': postcode,
            'city': city,
        }
        subtasks += create_chrome_shipping_work(input_kwargs, queue, bin=package)
        #add bin packages
        input_kwargs['packages'] = [package]
        packages_data.append(input_kwargs)

    if subtasks:
        subwork = group(*subtasks) | chrome_process_intl_shipping_methods\
            .s(packages_data, no_data_items, flash_messages, to_country)\
            .set(soft_timeout=10, queue=queue)
        return subwork()
    #we're dealing only with products with no additional data
    return None

@app.task(soft_time_limit=30)
def get_amazon_items(amazon_items):
    """
    Need to run in 10 items batches
    """
    items_list = amazon_items.items()
    max_batches = math.ceil(len(items_list) / 10.0)
    batch_num = 0
    while batch_num < max_batches:
        batch_asin_numbers = ",".join(key for key, val in items_list[batch_num*10: (batch_num+1)*10])
        get_amazon_products_data(batch_asin_numbers, amazon_items)
        batch_num += 1
    return amazon_items


@app.task(soft_time_limit=30)
def split_items_into_bins(amazon_items, include_usps):
    """
    This function does 3 things:
    1 - Create Package objects for every item in the cart
    2 - Get suitable bins for the items
    3 - calculate shipping costs for each bin
    """
    USPS_MAX_GIRTH_PLUS_LENGTH = 78
    predefined_bins = [
        Package(size=(7, 8, 8), weight=D('0.48'), nosort=True),    #38
        Package(size=(8, 10, 12), weight=D('0.70'), nosort=True),  #48
        Package(size=(10, 12, 14), weight=D('1.02'), nosort=True), #58
        Package(size=(12, 14, 16), weight=D('1.40'), nosort=True), #68
        Package(size=(14, 14, 22), weight=D('1.81'), nosort=True), #78
        Package(size=(16, 18, 24), weight=D('2.50'), nosort=True), #92
        Package(size=(20, 20, 26), weight=D('3.35'), nosort=True), #106
    ]

    def filter_items(items):
        """
        This function returns a list of items that we were unable
        to collect data for them
        """
        titles = []
        for key, value in items.items():
            #in case length does not exist we can assume that
            #we couldn't get item's data
            if 'length' not in value:
                item = items.pop(key)
                try:
                    titles.append(item['title'])
                except KeyError:
                    pass
        return titles

    def create_packages(items):
        packages = []
        for key, value in items.iteritems():
            for _ in range(int(value['quantity'])):
                    packages.append(
                        Package(
                            size=(
                                value['height'],
                                value['width'],
                                value['length']
                            ),
                            upc=key,
                            title=value['title'],
                            value=value['value'],
                            weight=value['weight'],
                        )
                    )
        return packages

    def get_qualified_bins(predefined_bins):
        selected_predefined_bins = []
        for bin in predefined_bins:
            if include_usps == 'true' and bin.girth_plus_length() > USPS_MAX_GIRTH_PLUS_LENGTH:
                break
            selected_predefined_bins.append(bin)
        return selected_predefined_bins


    def split_packages_into_bins(packages, predefined_bins, bins_in_use):
        bins = []
        for bin in predefined_bins:
            bins.append(
                binpack(packages=packages, bin=bin, iterlimit=1000)
            )
        largest_bin = predefined_bins[-1]
        for bin_data, predefined_bin in zip(bins, predefined_bins):
            #we stop when we find that all items can be shipped in 1 bin
            #or all items in one largest package
            #in such case we pick the smallest bin
            packages_in_bin, rest = bin_data
            all_items_in_one_bin = len(packages_in_bin) == 1

            #we were able to pack some items or all items
            if all_items_in_one_bin:
                if predefined_bin == largest_bin or not rest:
                    #in case no rest packages found, we stop here
                    #as we found the optimal solution
                    bins_in_use.append({
                        'bin': predefined_bin,
                        'packages': packages_in_bin[0]
                    })
                    return rest
            else:
                if predefined_bin == largest_bin:
                    #we were unable to pack any item, return rest
                    if not packages_in_bin:
                        return rest
                    #we need to pick the largest bin and call this function again
                    #with all packages
                    bins_in_use.append({
                        'bin': predefined_bin,
                        'packages': packages_in_bin[0] #take first bin
                    })
                    #flatten the inner lists
                    new_packages = list(chain.from_iterable(packages_in_bin[1:])) + rest
                    return split_packages_into_bins(new_packages, predefined_bins, bins_in_use)

        #we should never end in here
        return []

    def set_package_info(package, amazon_items):
        item = amazon_items[package.upc]
        package.length = item.get('package_length', item['length'])
        package.height = item.get('package_height', item['height'])
        package.width = item.get('package_width', item['width'])
        package.weight = item.get('package_weight', item['weight'])

    def handle_1_package_bin(package, bin):
        bin.weight = package.weight
        bin.height = package.height
        bin.width = package.width
        bin.length = package.length
        package.weight = 0
        package.height = 0
        package.width = 0
        package.length = 0

    def align_packages_data(bins, rest, amazon_items):

        """
        This function handles cases where we ship only 1 item
        This is a special case where we need to switch to package dimensions and weight
        from item data, if a bin contains only 1 package, we set the bin's data to be the same as the
        package's data and zero the inner package size and weight
        """
        for bin in bins:
            num_packages = len(bin['packages'])
            if num_packages == 1:
                package = bin['packages'][0]
                bin = bin['bin']
                set_package_info(package, amazon_items)
                handle_1_package_bin(package, bin)

        for package in rest:
            set_package_info(package, amazon_items)

    #print amazon_items
    bins_in_use = []
    rest = []
    no_data_items = filter_items(amazon_items)
    if amazon_items:
        packages = create_packages(amazon_items)
        selected_predefined_bins = get_qualified_bins(predefined_bins)
        rest = split_packages_into_bins(
            packages=packages,
            predefined_bins=selected_predefined_bins,
            bins_in_use=bins_in_use)
        align_packages_data(bins_in_use, rest, amazon_items)
    #print bins_in_use
    #print rest
    return (bins_in_use, rest, no_data_items)
