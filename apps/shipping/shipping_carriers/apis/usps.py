from decimal import ROUND_CEILING, Decimal as D
import logging
import urllib2
from xml.etree.ElementTree import fromstring
from django.conf import settings
from django.template import Context, loader
from apps.shipping.exceptions import ShippingMethodDoesNotExist
from ..carriers import USPS

log = logging.getLogger('usps.calculator')

class BaseShipper(object):
    SUPPORTED_USPS_DOMESTIC_CODES = {

    }
    SUPPORTED_USPS_INTL_CODES = {
        #'14': 'First Class Mail International Large Envelope',
        #'4': 'Global Express Guaranteed',
        #'6': 'Global Express Guaranteed Non-Document Rectangular',
        #'7': 'Global Express Guaranteed Non-Document Non-Rectangular',
        #'10': 'Priority Mail Express International Flat Rate Envelope',
        #'8': 'Priority Mail International Flat-Rate Envelope',
        #'12': 'USPS GXG Envelopes',
        #'24': 'Priority Mail International DVD Flat Rate priced box',
        #'25': 'Priority Mail International Large Video Flat Rate priced box',
        #'27': 'Priority Mail Express International Padded Flat Rate Envelope',
        #'17': 'Priority Mail Express International Legal Flat Rate Envelope'
        '1':  'ExpressMailInternational',
        '2':  'PriorityMailInternational',
        '15': 'FirstClassPackageInternationalService',
    }

    def __init__(self, weight, length, width, height, value, api):
        self.value = value
        self.weight = weight
        self.length = length
        self.width = width
        self.height = height
        self.api = api

    def align_package_dimensions(self):
        #length is the longest dimension
        longest_dim = max(self.width, self.height, self.length)
        if longest_dim != self.length:
            if longest_dim == self.width:
                tmp_dim = self.width
                self.width = self.length
            else:
                tmp_dim = self.height
                self.height = self.length
            self.length = tmp_dim

    def process_request(self, connection, request):
        """
        Post the data and return the XML response
        we always ship international
        """
        data = 'API=%s&XML=%s' % (self.api, request.encode('utf-8'))

        conn = urllib2.Request(url=connection, data=data)
        f = urllib2.urlopen(conn, timeout=5)
        all_results = f.read()

        log.debug(all_results)
        return fromstring(all_results)

class UspsAPICalculator(BaseShipper):
    template = 'shipping/usps/request_intl.xml'

    def __init__(self, to_country, weight, length, width, height, value):
        self.to_country = to_country
        super(UspsAPICalculator, self).__init__(weight, length,
                                                width, height, value, 'IntlRateV2')

    def __str__(self):
        """
        This is mainly helpful for debugging purposes
        """
        return "U.S. Postal Service International Calculator"

    def __unicode__(self):
        return u"U.S. Postal Service International Calculator"

    def render_template(self, template):
        #length must be the longest dimension
        #this function aligns it
        self.align_package_dimensions()

        size = 'REGULAR'
        if self.width > 12 or self.length > 12 or self.height > 12:
            size = 'LARGE'

        log.debug('WIDTH: %s, LENGTH: %s, HEIGHT: %s, WEIGHT: %s VALUE: %s' %
                  (self.width, self.length, self.height, self.weight, self.value))

        c = Context({
                'userid': settings.USPS_USER_ID,
                'value_of_content': self.value,
                'weight': self.weight,
                'country': self.to_country.printable_name,
                'width': self.width,
                'length': self.length,
                'height': self.height,
                'size': size
        })

        t = loader.get_template(template)
        return t.render(c)


    def retrieveShippingOptions(self):
            """
            We will do our call to USPS and see how
            much it will cost. We will also need to store the results for further
            parsing and return via the methods above
            we will store all relevant shipping options
            """
            shipping_options = []

            request = self.render_template(self.template)

            #always use the production address for int queries
            connection = settings.USPS_CONNECTION_ADDR

            log.debug("USPS URL: %s", connection)
            log.debug("Requesting from USPS\n%s", request)

            try:
                tree = self.process_request(connection, request)
            except Exception:
                return shipping_options

            errors = tree.getiterator('Error')

            # if USPS returned no error, return the prices
            if errors is None or len(errors) == 0:
                    all_packages = tree.getiterator('IntlRateV2Response')
                    for package in all_packages:
                        for service in package.getiterator('Service'):
                            service_id = service.attrib['ID']
                            try:
                                service_name = self.SUPPORTED_USPS_INTL_CODES[service_id]
                            except KeyError:
                                #service_name = HTMLParser.HTMLParser().unescape(service.find('.//SvcDescription').text)
                                #service_name = re.sub(r'<sup>.*</sup>', '', service_name)
                                #service_name = re.sub(r'[^a-zA-Z0-9 ]', '', service_name)
                                #log.info("Found new service name: %s, ID: %s" % (service_name, service_id))
                                continue

                            #Get online charges (if available)
                            charges = service.find('.//CommercialPostage')
                            if charges is None or charges.text is None:
                                charges = service.find('.//Postage')

                            #check that we got total charge
                            if charges is None or charges.text is None:
                                log.error("USPS calculator could not fetch total shipping charge for: %s" % service_name)
                                continue

                            #insurance_available = False
                            #insurance_charges = '0.0'

                            #calculate insurance
                            #for extra_service in service.getiterator('ExtraService'):
                            #    extra_service_name = extra_service.find('.//ServiceName').text
                            #    available = extra_service.find('.//Available').text
                            #    if 'Insurance' == extra_service_name and available == 'True':
                            #        insurance_charges = extra_service.find('.//Price').text
                            #        insurance_available = True
                            #        log.debug('insurance price is: %s' % insurance_charges)
                            #        break

                            #delivery_days = service.find('.//SvcCommitments').text
                            #delivery_days = re.sub(r'business days', '', delivery_days)

                            #if delivery_days == 'Varies by destination':
                            #    delivery_days = '14 - 21'
                            log.debug('%s: charge:%s' % (service_name, charges.text))

                            kwargs = {
                               'ship_charge_excl_revenue': D(charges.text),
                               'service_code': service_name,
                               'country_code': self.to_country.iso_3166_1_a2,
                               'contents_value': self.value
                            }
                            try:
                                shipping_option = USPS(**kwargs)
                            except ShippingMethodDoesNotExist:
                                pass
                            else:
                                shipping_options.append(shipping_option)
            else:
                for error in errors:
                    err_num = error.find('.//Number').text
                    description = error.find('.//Description').text
                    log.error("USPS Error: Code %s: %s" % (err_num, description))

            return shipping_options


class UspsShipperDomesticCalculator(BaseShipper):
    template = 'shipping/usps/request_domestic.xml'

    def __init__(self, zip_org, zip_dst, weight, length, width, height, value):
        self.zip_org = zip_org
        self.zip_dst = zip_dst
        super(UspsShipperDomesticCalculator, self).__init__(weight, length,
                                                            width, height, value, 'RateV4')
    def __str__(self):
        """
        This is mainly helpful for debugging purposes
        """
        return "U.S. Postal Service Domestic Calculator"

    def __unicode__(self):
        return u"U.S. Postal Service Domestic Calculator"

    def render_template(self, template):
        #length must be the longest dimension
        #this function aligns it
        self.align_package_dimensions()
        #align to int
        #align to int
        width = self.width.to_integral_exact(rounding=ROUND_CEILING)
        length = self.length.to_integral_exact(rounding=ROUND_CEILING)
        height = self.height.to_integral_exact(rounding=ROUND_CEILING)

        size = 'REGULAR'
        if width > 12 or length > 12 or height > 12:
            size = 'LARGE'

        log.debug('WIDTH: %s, LENGTH: %s, HEIGHT: %s, WEIGHT: %s VALUE: %s' % (width, length, height, self.weight, self.value))
        c = Context({
                'userid': settings.USPS_USER_ID,
                'value_of_content': self.value,
                'weight': self.weight,
                'org_zip': self.zip_org,
                'dst_zip': self.zip_dst,
                'width': width,
                'length': length,
                'height': height,
                'size': size
        })

        t = loader.get_template(template)
        return t.render(c)


    def calculateShippingOptions(self):
            """
            We will do our call to USPS and see how
            much it will cost. We will also need to store the results for further
            parsing and return via the methods above
            we will store all relevant shipping options
            """
            shipping_options = []

            request = self.render_template(self.template)

            #always use the production address for int queries
            connection = settings.USPS_CONNECTION_ADDR

            log.debug("USPS URL: %s", connection)
            log.debug("Requesting from USPS\n%s", request)

            tree = self.process_request(connection, request)

            errors = tree.getiterator('Error')

            # if USPS returned no error, return the prices
            if errors is None or len(errors) == 0:
                    all_packages = tree.getiterator('RateV4Response')
                    for package in all_packages:
                        for postage in package.getiterator('Postage'):
                            postage_id = postage.attrib['CLASSID']
                            try:
                                service_name = self.SUPPORTED_USPS_DOMESTIC_CODES[postage_id]
                            except KeyError:
                                #service_name = HTMLParser.HTMLParser().unescape(postage.find('.//MailService').text)
                                #service_name = re.sub(r'<sup>.*</sup>', '', service_name)
                                #service_name = re.sub(r'[^a-zA-Z0-9 ]', '', service_name)
                                #log.info("Found new service name: %s" % service_name)
                                continue

                            charges = postage.find('.//Rate').text
                            #check that we got total charge
                            if not charges:
                                log.error("USPS calculator could not fetch total shipping charge for: %s" % service_name)
                                continue

                            log.debug('%s: charge:%s' % (service_name, charges))

                            kwargs = {
                               'ship_charge_excl_revenue': D(charges),
                               'service_code': service_name,
                               'country_code': 'US',
                               'contents_value': self.value
                            }
                            try:
                                shipping_option = USPS(**kwargs)
                            except ShippingMethodDoesNotExist:
                                pass
                            else:
                                shipping_options.append(shipping_option)
            else:
                for error in errors:
                    err_num = error.find('.//Number').text
                    description = error.find('.//Description').text
                    log.error("USPS Error: Code %s: %s" % (err_num, description))

            return shipping_options
