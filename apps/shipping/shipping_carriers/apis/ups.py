######################################################################
#    TAKEN FROM:                                                     #
#    https://github.com/benweatherman/python-ship/blob/master/ups.py #
######################################################################
from django.conf import settings
from apps.shipping.exceptions import ShippingMethodDoesNotExist
from decimal import Decimal as D
import math
import logging
from ..carriers import UPS
import os
import suds
from suds.client import Client
from suds.sax.element import Element
from suds.plugin import MessagePlugin
import urllib
import urlparse


logger = logging.getLogger('management_commands')


SERVICES = [
    ('03', 'Ground'),
    ('11', 'UPSStandard'),
    ('01', 'Next Day'),
    ('14', 'Next Day AM'),
    ('13', 'Next Day Air Saver'),
    ('02', '2nd Day'),
    ('59', '2nd Day AM'),
    ('12', '3-day Select'),
    ('65', 'UPSSaver'),
    ('07', 'Express'),
    ('08', 'Expedited'),
    ('54', 'ExpressPlus'),
    ('96', 'Worldwide Express Freight'),
]

def recurseElement(element, search, replace):
	if search == element.qname():
		element.rename(replace)
	if element.isempty != True:
		for x in element.getChildren():
			recurseElement(x,search,replace)
	return

class SoapClient(object):
    pass

class FixRequestNamespacePlug(MessagePlugin):
    #marshalled seems to actually replace properly here, wheras sending does not seem to actually replace properly (bug?)
    def marshalled(self, context):
        element = context.envelope.getChild('Body')
        #context.envelope = context.envelope.replace('ns1:Request>', 'ns0:Request>').replace('ns2:Request>', 'ns1:Request>')
        recurseElement(element,'ns1:Request','ns0:Request')
        recurseElement(element,'ns2:Request','ns1:Request')
        return context


class UPSAPICalculator(object):
    def __init__(self, to_country, postcode, weight, length, width, height, value, partner_name):
        self.credentials = {
            'username': settings.UPS_ACCOUNT_KEY[partner_name],
            'password': settings.UPS_ACCOUNT_PASSWORD[partner_name],
            'shipper_number': settings.UPS_ACCOUNT_NUMBER[partner_name],
            'access_license': settings.UPS_ACCESS_LICENSE[partner_name]
        }
        self.wsdl_dir = os.path.join(settings.TEMPLATE_DIRS[0], 'shipping/ups')
        self.country_code = to_country.iso_3166_1_a2
        self.weight = float(weight)
        self.width = width
        self.length = length
        self.height = height
        self.value = value
        self.postcode = postcode
        self.partner_name = partner_name

    def _add_security_header(self, client):
        security_ns = ('security', 'http://www.ups.com/XMLSchema/XOLTWS/UPSS/v1.0')
        security = Element('UPSSecurity', ns=security_ns)

        username_token = Element('UsernameToken', ns=security_ns)
        username = Element('Username', ns=security_ns).setText(self.credentials['username'])
        password = Element('Password', ns=security_ns).setText(self.credentials['password'])
        username_token.append(username)
        username_token.append(password)

        service_token = Element('ServiceAccessToken', ns=security_ns)
        license = Element('AccessLicenseNumber', ns=security_ns).setText(self.credentials['access_license'])
        service_token.append(license)

        security.append(username_token)
        security.append(service_token)

        client.set_options(soapheaders=security)


    def wsdlURL(self, wsdl_name):
        wsdl_file_path = os.path.join(self.wsdl_dir, wsdl_name)
        # Get the os specific url to deal with windows drive letter
        wsdl_file_url = urllib.pathname2url(wsdl_file_path)
        wsdl_url = urlparse.urljoin('file://', wsdl_file_url)
        return wsdl_url

    def _get_client(self, wsdl):
        wsdl_url = self.wsdlURL(wsdl)
        # Setting prefixes=False does not help
        return Client(wsdl_url, plugins=[FixRequestNamespacePlug()])
        #Loading with ship.wsdl gives this:
        #ns0 = "http://www.ups.com/XMLSchema/XOLTWS/Common/v1.0"
      	#ns1 = "http://www.ups.com/XMLSchema/XOLTWS/Error/v1.1"
     	#ns2 = "http://www.ups.com/XMLSchema/XOLTWS/IF/v1.0"
      	#ns3 = "http://www.ups.com/XMLSchema/XOLTWS/Ship/v1.0"

    def soapClient(self, wsdl):
        wsdl_url = self.wsdlURL(wsdl)
        return SoapClient(wsdl=wsdl_url, trace=True)

    def _create_shipment(self, client):
        shipment = client.factory.create('{0}:ShipmentType'.format('ns2'))
        shipper_country = 'US'

        package = client.factory.create('{0}:PackageType'.format('ns2'))

        if hasattr(package, 'Packaging'):
            package.Packaging.Code = '02' #Custom Packaging
        elif hasattr(package, 'PackagingType'):
            package.PackagingType.Code = '02' #Custom Packaging
        else:
            logger.error("Can't set packagin type")
            return None

        package.Dimensions.UnitOfMeasurement.Code = 'IN'
        if (self.length == 0) or (self.width == 0) or (self.height == 0):
            logger.error('Dimensions',"Packaging dimensions are required if packaging type is custom")
            return None

        package.Dimensions.Length = int(math.ceil(self.length))
        package.Dimensions.Width = int(math.ceil(self.width))
        package.Dimensions.Height = int(math.ceil(self.height))

        package.PackageWeight.UnitOfMeasurement.Code = 'LBS'
        package.PackageWeight.Weight = self.weight

        #if can_add_delivery_confirmation and p.require_signature:
        #    package.PackageServiceOptions.DeliveryConfirmation.DCISType = str(p.require_signature)

        if self.value:
            package.PackageServiceOptions.DeclaredValue.CurrencyCode = 'USD'
            package.PackageServiceOptions.DeclaredValue.MonetaryValue = self.value

        shipment.Package.append(package)

        # Fill in Shipper information
        shipment.Shipper.Address.PostalCode = '92705'
        shipment.Shipper.Address.CountryCode = shipper_country
        shipment.Shipper.Address.StateProvinceCode = 'CA'
        shipment.Shipper.ShipperNumber = self.credentials['shipper_number']

        # Fill in ShipFrom information
        shipment.ShipFrom.Address.PostalCode = '92705'
        shipment.ShipFrom.Address.CountryCode = shipper_country
        shipment.ShipFrom.Address.StateProvinceCode = 'CA'

        # Fill in ShipTo information
        shipment.ShipTo.Address.PostalCode = self.postcode
        shipment.ShipTo.Address.CountryCode = self.country_code

        #mark residential address
        shipment.ShipTo.Address.ResidentialAddressIndicator = ''

        #ask for negotiated rates
        shipment.ShipmentRatingOptions.NegotiatedRatesIndicator = '1'

        return shipment

    def retrieveRates(self):
        shipping_options = []

        client = self._get_client('RateWS.wsdl')
        self._add_security_header(client)
        client.set_options(location='https://onlinetools.ups.com/webservices/Rate')

        request = client.factory.create('ns0:RequestType')
        request.RequestOption = 'Shop'

        classification = client.factory.create('ns2:CodeDescriptionType')
        classification.Code = '01' # Get rates for the shipper account
        classification.Description = 'Classification'  # Get rates for the shipper account

        pickup = client.factory.create('ns2:CodeDescriptionType')
        pickup.Code = '06' # One Time Pickup

        shipment = self._create_shipment(client)

        try:
            self.reply = client.service.ProcessRate(request,
                                                    CustomerClassification=classification,
                                                    PickupType=pickup,
                                                    Shipment=shipment)
            #print self.reply
            service_lookup = dict(SERVICES)
            for service in self.reply.RatedShipment:
                try:
                    rate = service.NegotiatedRateCharges.TotalCharge.MonetaryValue
                except AttributeError:
                    rate = service.TotalCharges.MonetaryValue
                kwargs = {
                    'ship_charge_excl_revenue': D(str(rate)),
                    'service_code': service_lookup.get(service.Service.Code),
                    'country_code': self.country_code,
                    'contents_value': self.value
                }
                try:
                    shipping_option = UPS(**kwargs)
                except ShippingMethodDoesNotExist:
                    continue

                #surcharges = []
                #on_pickup_charge = D('0.0')

                #for detail in service.RatedShipmentDetails:
                #    #print detail.ShipmentRateDetail.Surcharges
                #    for surcharge in detail.ShipmentRateDetail.Surcharges:
                #        if surcharge.Description == 'On call pickup':
                #            on_pickup_charge = D(str(surcharge.Amount.Amount))
                #        surcharges.append((surcharge.Description, surcharge.Amount.Amount))
                #shipping_option.add_surcharges(surcharges)
                #dirty patch that removes the on call pickup surcharge for GLOBAL and PREFERRED
                #- they have a free daily pickup
                #and their FedEx account returns this surcharge accidentally
                #if self.partner_name in [settings.GLOBAL, settings.PREFERRED]:
                #    shipping_option.ship_charge_excl_revenue -= on_pickup_charge
                shipping_options.append(shipping_option)
        except suds.WebFault as e:
            pass
            #log.critical("Fedex API response error: no RateReplyDetails found,"
            #             " postal code: %s, country: %s" % (self.postcode, self.country_code))
        return shipping_options


