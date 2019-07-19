from decimal import ROUND_CEILING, Decimal as D
from collections import OrderedDict
import logging
import math
from apps.user.utils import get_warehouse_address
import easypost
from django.conf import settings
from apps.shipping.shipping_carriers.carriers import (
    USPS, FedEx, TNTExpress, UPS, Aramex, DHL)
from .exceptions import ShippingMethodDoesNotExist
from apps.address import utils
from shipping_carriers.apis.aramex import AramexAPICalculator
from shipping_carriers.apis.dhl import DHLAPICalculator


ONEPLACE = D('0.1')
logger = logging.getLogger("management_commands")
easypost_logger = logging.getLogger("easypost")
PREDEFINED_PACKAGE_DOMESTIC_NO_MATCH = 'NoFlatRateBoxDomesticOnly'

class EasyPostAPI(object):
    #DOMESTIC_METHODS_RESTRICTIONS = {
    #    'USPS': {
    #        'Express': {'weight': 70, 'length_and_girth': 108},
    #        'Priority': {'weight': 70, 'length_and_girth': 108},
    #        'First': {'weight': 0.81, 'length_and_girth': 108},
    #        'ParcelSelect': {'weight': 70, 'length_and_girth': 108}
    #    }
    #}

    FLAT_RATE_PACKAGES_DOMESTIC_ONLY = {
        'USPS': [
            OrderedDict([
                ('SmallFlatRateBox', [
                    {'length': D('8.62'), 'width': D('5.37'), 'height': D('1.62')}
                ]),
                ('MediumFlatRateBox', [
                    {'length': D('11'), 'width': D('8.5'), 'height': D('5.5')},
                    {'length': D('13.62'), 'width': D('11.87'), 'height': D('3.37')}
                ]),
                ('LargeFlatRateBox', [
                    {'length': D('12'), 'width': D('12'), 'height': D('5.5')}
                ]),
                ('LargeFlatRateBoardGameBox', [
                    {'length': D('23.68'), 'width': D('11.75'), 'height': D('3')}
                ])
            ]),
            OrderedDict([
                ('RegionalRateBoxA', [
                    {'weight': D('15.0'), 'length': D('10'), 'width': D('7'), 'height': D('4.75')},
                    {'weight': D('15.0'), 'length': D('12.81'), 'width': D('10.93'), 'height': D('2.37')}
                ]),
                ('RegionalRateBoxB', [
                    {'weight': D('20.0'), 'length': D('12'), 'width': D('10.25'), 'height': D('5')},
                    {'weight': D('20.0'), 'length': D('15.87'), 'width': D('14.37'), 'height': D('2.87')}
                ]),
                ('RegionalRateBoxC',  [
                    {'weight': D('25.0'), 'length': D('14.75'), 'width': D('11.75'), 'height': D('11.5')}
                ])
            ])
        ],
    }

    def __init__(self, api_key=None):
        easypost.api_key = api_key or settings.EASYPOST_API_KEY

    @staticmethod
    def _convert_lbs_to_oz(lbs):
        return lbs * D('16')

    @staticmethod
    def _make_address_args(addr, email=None, company=None, name=None):
        ret = {
            "street1": addr.line1,
            "street2": addr.line2,
            "city": addr.city,
            "state": addr.state if addr.state else '',
            "zip": addr.postcode,
            "country": addr.country.iso_3166_1_a2,
            "email": email if email else ''
        }

        if addr.phone_number:
            if utils.is_domestic_delivery(ret['country']):
                ret['phone'] = addr.phone_number.as_national
            else:
                ret['phone'] = addr.phone_number.as_international

        if company:
            ret["company"] = company

        if name:
            ret["name"] = name
        else:
            ret["name"] = addr.name

        return ret

    @staticmethod
    def create_insurance(shipment, amount):
        return shipment.insure(amount=amount).insurance

    def create_batch_and_buy(self, shipments):
        return easypost.Batch.create(shipment=shipments)

    @staticmethod
    def validate_package_dimensions(predefined_packages, weight, length, width, height, value):
        for predefined_package in predefined_packages:
            pre_width = predefined_package.get('width', width)
            pre_weight = predefined_package.get('weight', weight)
            pre_length = predefined_package.get('length', length)
            pre_height = predefined_package.get('height', height)
            pre_value = predefined_package.get('value', value)

            if weight <= pre_weight and length <= pre_length and \
               height <= pre_height and width <= pre_width and value <= pre_value:
                return True

        return False

    def _match_predefined_items(self, weight, length, height, width, value, items, no_match_value):
        for key, predefined_package in items:
            if self.validate_package_dimensions(
                predefined_packages=predefined_package,
                weight=weight,
                length=length,
                height=height,
                width=width,
                value=value
            ):
                return key

        return no_match_value

    def get_predefined_domestic_only_package(self, group, weight, length, width, height, value):
        #check all predefined boxes
        items = group.items()
        return self._match_predefined_items(weight, length, height,
                                            width, value, items, PREDEFINED_PACKAGE_DOMESTIC_NO_MATCH)

    def _create_from_address(self, partner, customer_uuid=None, package_upc=None, partner_company=None):
        """
        return easypost from address which is based on admin address
        """
        uuid_and_upc = None
        facilities_addrs = get_warehouse_address(partner=partner)
        if facilities_addrs:
            #currently we only have 1 storage
            facility_addr = facilities_addrs[0]
            if customer_uuid and package_upc:
                uuid_and_upc = "%(suite_num)s-%(package_id)s" % {
                    'suite_num': customer_uuid,
                    'package_id': package_upc
                }
                facility_addr.line2 = facility_addr.line2 % uuid_and_upc

            # no need to include partner company name, therefore we only use the company field
            if not partner_company:
                company = settings.OSCAR_SHOP_NAME
                name = None
                if uuid_and_upc:
                    company = "{} {}".format(company, uuid_and_upc)
            # we need to include partner company name, therefore we use both the company and name fields
            else:
                company = partner_company
                name = "c/o {}".format(settings.OSCAR_SHOP_NAME)
                if uuid_and_upc:
                    name = "{} {}".format(name, uuid_and_upc)

            kwargs = self._make_address_args(
                addr=facility_addr,
                email=settings.EASYPOST_FROM_ADDRESS_EMAIL,
                company=company,
                name=name
            )

            return kwargs

        return None

    def _create_to_address(self, shipping_addr, email):
        return self._make_address_args(addr=shipping_addr, email=email)

    def _create_parcel(self, weight, length, width, height, predefined_package=None):
        #make sure all go to one decimal point
        #weight should be converted from lbs to oz
        oz_weight = self._convert_lbs_to_oz(weight)
        kwargs = {
            "weight": float(oz_weight.quantize(ONEPLACE, rounding=ROUND_CEILING))
        }

        if predefined_package is None:
            kwargs.update({
                "length": float(length.quantize(ONEPLACE, rounding=ROUND_CEILING)),
                "width":  float(width.quantize(ONEPLACE, rounding=ROUND_CEILING)),
                "height": float(height.quantize(ONEPLACE, rounding=ROUND_CEILING))
            })
        else:
            kwargs.update({
                'predefined_package': predefined_package
            })
        return kwargs

    def _create_customs_items(self, customs_form, total_weight):
        custom_items = []
        oz_weight = self._convert_lbs_to_oz(total_weight)
        customs_form_items = list(customs_form.items.all())
        num_of_items = len(customs_form_items)
        item_weight = float((oz_weight / D(num_of_items)).quantize(ONEPLACE, rounding=ROUND_CEILING))
        weight = D('0.0')

        for i, item in enumerate(customs_form_items):
            #align weight for last item
            if i == (num_of_items - 1):
                item_weight = float((oz_weight - weight).quantize(ONEPLACE, rounding=ROUND_CEILING))
            custom_item = {
                "description": item.description,
                "quantity": item.quantity,
                "value": float(item.value.quantize(ONEPLACE, rounding=ROUND_CEILING)),
                "hs_tariff_number": item.hs_tariff_number or '',
                "weight": item_weight,
                "origin_country": 'US'
            }
            weight += D(str(item_weight))
            custom_items.append(custom_item)

        return custom_items

    def _create_customs_object(self, customs_form, customer_name, total_weight,
                               itn_number=None, contents_explanation=None):
        custom_info = {
            "eel_pfc": itn_number or 'NOEEI 30.37(a)',
            "customs_certify": True,
            "customs_signer": customer_name,
            "non_delivery_option": 'abandon',
            "contents_explanation": contents_explanation or '',
            "restriction_type": 'none'
        }
        custom_info["contents_type"] = customs_form.content_type.lower().replace(" ", "_")
        customs_items = self._create_customs_items(customs_form, total_weight)
        custom_info["customs_items"] = customs_items
        return custom_info

    def _create_shipping_method(self, carrier, value, service, rate, country_code):
        carriers_pool = {
            settings.EASYPOST_USPS: USPS,
            settings.EASYPOST_FEDEX: FedEx,
            settings.EASYPOST_TNTEXPRESS: TNTExpress,
            settings.EASYPOST_UPS: UPS,
            settings.EASYPOST_ARAMEX: Aramex,
            settings.EASYPOST_DHL: DHL,
        }
        method = None
        shipping_insurance_cost = self.calculate_shipping_insurance_cost(value)
        kwargs = {
            'ship_charge_excl_revenue': D(rate),
            'service_code': service,
            'insurance_charge': D(shipping_insurance_cost),
            'country_code': country_code,
            'contents_value': value
        }
        try:
            method = carriers_pool[carrier](**kwargs)
        except ShippingMethodDoesNotExist:
            logger.warning("Found new shipping method: %s" % service)
        except KeyError:
            logger.error("Found unrecognized carrier: %s" % carrier)
        return method

    def partner_supported_carriers(self, partner, excluded_carriers=None):
        supported_carriers = partner.supported_carriers()
        carrier_accounts = []
        for supported_carrier in supported_carriers:
            if excluded_carriers and supported_carrier in excluded_carriers:
                continue
            try:
                carrier_accounts.append({
                    'id': settings.EASYPOST_CARRIER_ACCOUNTS[partner.name][supported_carrier]
                })
            except KeyError:
                pass
        return carrier_accounts

    def _create_shipment_args(self, weight, length, width, height,
                              predefined_parcel, country_code,
                              postcode, customs_form, partner, **kwargs):
        shipment_kwargs = {}
        shipping_addr = kwargs.get('shipping_address')
        city = kwargs.get('city')

        if not city and shipping_addr:
            city = shipping_addr.city

        from_address = self._create_from_address(partner=partner)
        to_address = {'country': country_code}

        if city:
            try:
                to_address['city'] = str(city)
            except UnicodeEncodeError:
                pass
            else:
                to_address['street1'] = 'rotshield 7' if shipping_addr is None else shipping_addr.line1

        if postcode:
            to_address['zip'] = postcode

        if customs_form is not None:
            customs_info = self._create_customs_object(
                customs_form=customs_form,
                customer_name="",
                total_weight=weight
            )
            shipment_kwargs['customs_info'] = customs_info
        else:
            #hack to get Aramex rates
            customs_info = {
                "eel_pfc": 'NOEEI 30.37(a)',
                "customs_certify": True,
                "customs_signer": '',
                "contents_explanation": '',
                "restriction_type": 'none'
            }
            customs_info["contents_type"] = 'merchandise'
            customs_info['customs_items'] = [{
                "description": 'iPad',
                "quantity": 1,
                "value": 100,
                "weight": 32,
                "origin_country": 'US'
            }]
            shipment_kwargs['customs_info'] = customs_info

        parcel = self._create_parcel(weight, length, width, height, predefined_parcel)
        shipment_kwargs['parcel'] = parcel
        shipment_kwargs['to_address'] = to_address
        shipment_kwargs['from_address'] = from_address

        #ask for partner supported carriers rates only
        excluded_carriers = self.get_excluded_carriers(city=city, country_code=country_code, weight=weight)
        shipment_kwargs['carrier_accounts'] = self.partner_supported_carriers(partner, excluded_carriers)
        return shipment_kwargs

    def get_excluded_carriers(self, **kwargs):
        """
        At the moment we have restrictions only for Aramex and DHL, we filter such companies out to save
        some processing time
        """
        excluded_carriers = []
        if not AramexAPICalculator.carrier_allowed(**kwargs):
            excluded_carriers.append(settings.EASYPOST_ARAMEX)
        if not DHLAPICalculator.carrier_allowed(**kwargs):
            excluded_carriers.append(settings.EASYPOST_DHL)
        return excluded_carriers


    def calculate_flat_rate_methods(self, weight, length, width, height,
                                    value, predefined_parcel, to_country,
                                    postcode, customs_form, partner, **kwargs):
        flat_rate_methods = []
        country_code = to_country.iso_3166_1_a2
        shipment_args = self._create_shipment_args(weight, length, width, height,
                                                   predefined_parcel, country_code,
                                                   postcode, customs_form, partner)
        try:
            predefined_parcel_shipment = easypost.Shipment.create(**shipment_args)
        except easypost.Error as e:
            logger.critical('Could not fetch rates through EasyPost %s' % e.message)
            return flat_rate_methods

        try:
            predefined_parcel_rates = predefined_parcel_shipment["rates"]
        except KeyError:
            predefined_parcel_rates = []

        for predefined_parcel_rate in predefined_parcel_rates:
            #change service name to mark it as flat rate box
            try:
                predefined_parcel_rate['service'] += "-" + predefined_parcel
            except KeyError:
                logger.critical("EasyPost predefined package has no service key")
            else:
                method = self._create_shipping_method('USPS', value, predefined_parcel_rate["service"],
                                                      predefined_parcel_rate["rate"], country_code)
                if method:
                    flat_rate_methods.append(method)

        return flat_rate_methods

    def create_shipment(self, package_upc, shipping_addr, weight, length,
                        width, height, customs_form, customer_name,
                        service, carrier, customer_uuid, email,
                        partner, itn_number, contents_explanation, **kwargs):
        ret = {"reference": package_upc, "carrier": carrier}
        is_domestic = utils.is_domestic_delivery(shipping_addr.country.iso_3166_1_a2)
        to_address = self._create_to_address(shipping_addr=shipping_addr, email=email)
        form_address_kwargs = {
            'partner': partner,
            'customer_uuid': customer_uuid,
            'package_upc': package_upc
        }

        # special handling for Aramex shipments where we must include the partner name on
        # the label and commercial invoice
        if carrier == settings.EASYPOST_ARAMEX:
            form_address_kwargs['partner_company'] = settings.ACTIVE_PARTNER_COMPANY_NAME

        from_address = self._create_from_address(**form_address_kwargs)

        tokens = service.split('-')
        service = tokens[0]
        try:
            predefined_package = tokens[1]
        except IndexError:
            predefined_package = None

        parcel = self._create_parcel(
            weight=weight,
            length=length,
            width=width,
            height=height,
            predefined_package=predefined_package
        )

        ret['to_address'] = to_address
        ret['from_address'] = from_address
        ret['parcel'] = parcel
        ret['service'] = service
        ret['options'] = {'delivered_duty_paid': False} #,'label_format': 'PNG'}
        ret['carrier_accounts'] = self.partner_supported_carriers(partner)

        #special treatment for TNT - only native PDF works
        if carrier == settings.EASYPOST_TNTEXPRESS:
            ret['options']['label_format'] = 'PDF'

        if carrier == settings.EASYPOST_DHL:
            ret['options']['incoterm'] = 'DAP'

        #mark that shipment contains lithium batteries
        #if lithium_battery_exists:
        #    ret['options']['hazmat'] = 'ORMD'

        #we take this option down for now as it costs $4 more
        #if carrier in settings.EASYPOST_EXPRESS_CARRIERS:
        #    ret['options']['delivery_confirmation'] = 'ADULT_SIGNATURE'

        #only international shipment needs customs form declarations
        if not is_domestic:
            if not customs_form:
                #should not get there!!!
                logger.critical("International shipment with no customs declaration, customer uuid %s"
                                % customer_uuid)
                return None
            else:
                customs_info = self._create_customs_object(
                    customs_form=customs_form,
                    customer_name=customer_name,
                    total_weight=weight,
                    itn_number=itn_number,
                    contents_explanation=contents_explanation
                )
                ret['customs_info'] = customs_info

        return ret

    def calculate_shipping_insurance_cost(self, total_value):
        return D(math.ceil(total_value / D('100.0')))

    def calculate_intl_shipping_rates(self, weight, length, width,
                                      height, value, to_country,
                                      postcode, customs_form, partner, **kwargs):
        shipping_methods = []
        country_code = to_country.iso_3166_1_a2
        shipping_addr = kwargs.get('shipping_address')
        shipment_args = self._create_shipment_args(weight, length, width, height,
                                                   None, country_code,
                                                   postcode, customs_form, partner,
                                                   shipping_address=shipping_addr,
                                                   city=kwargs.get('city'))
        try:
            shipment = easypost.Shipment.create(**shipment_args)
            if not settings.DEBUG:
                # log the shipment
                easypost_logger.info("Created EasyPost shipment: %s, args = %s", shipment['id'], shipment_args)
        except easypost.Error as e:
            logger.critical('Could not fetch rates through EasyPost %s' % e.message)
            return shipping_methods

        try:
            rates = shipment["rates"]
            #print rates
            #print shipment
            #print shipment.messages

            for rate in rates:
                method = self._create_shipping_method(rate["carrier"], value, rate["service"],
                                                      rate["rate"], country_code)
                if method:
                    shipping_methods.append(method)
        except KeyError:
            pass

        return shipping_methods

    def calculate_domestic_shipping_rates(self, weight, length, width, height,
                                          value, postcode, to_country,
                                          customs_form, partner, **kwargs):
        """
        Return only USPS services
        """
        shipping_methods = []
        country_code = to_country.iso_3166_1_a2
        shipment_args = self._create_shipment_args(weight, length, width, height,
                                                   None, country_code,
                                                   postcode, customs_form, partner)
        try:
            shipment = easypost.Shipment.create(**shipment_args)
        except easypost.Error as e:
            logger.critical('Could not fetch rates through EasyPost %s' % e.message)
            return shipping_methods

        try:
            rates = shipment["rates"]
            for rate in rates:
                method = self._create_shipping_method(rate['carrier'], value, rate['service'],
                                                      rate['rate'], 'US')
                if method and method.carrier == 'USPS':
                    shipping_methods.append(method)
        except KeyError:
            pass

        return shipping_methods

    def align_package_dimensions(self, length, width, height):
        #length is the longest dimension
        longest_dim = max(width, height, length)
        if longest_dim != length:
            if longest_dim == width:
                tmp_dim = width
                width = length
            else:
                tmp_dim = height
                height = length
            length = tmp_dim
        return length, width, height

    def get_domestic_flat_methods(self, weight, length, width, height, value, carrier='USPS'):
        #check for flat rate domestic boxes
        predefined_domestic_packages = []
        #length must be the longest dimension
        length, width, height = self.align_package_dimensions(length, width, height)

        for group in self.FLAT_RATE_PACKAGES_DOMESTIC_ONLY[carrier]:
            predefined_domestic_package = self.get_predefined_domestic_only_package(group, weight, length,
                                                                                    width, height, value)
            if predefined_domestic_package != PREDEFINED_PACKAGE_DOMESTIC_NO_MATCH:
                predefined_domestic_packages.append(predefined_domestic_package)

        return predefined_domestic_packages

    def retrieve_shipment(self, shipment_id):
        return easypost.Shipment.retrieve(easypost_id=shipment_id)

    def retrieve_batch(self, batch_id):
        return easypost.Batch.retrieve(easypost_id=batch_id)

    @staticmethod
    def remove_failed_shipments(batch):
        failed = 0

        for s in batch.shipments:
            if s.batch_status == 'postage_purchase_failed':
                logger.error("EasyPost removed failed shipment msg = %s" % s.batch_message)
                batch.remove_shipments(shipment=[s])
                failed += 1
        return failed



















