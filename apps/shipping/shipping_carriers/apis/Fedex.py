from fedex.services.rate_service import FedexRateServiceRequest
from fedex.config import FedexConfig
from django.conf import settings
from apps.shipping.exceptions import ShippingMethodDoesNotExist
from ..carriers import FedEx
from decimal import Decimal as D
import math
import logging
import datetime

log = logging.getLogger('management_commands')

class FedexAPICalculator(object):
    def __init__(self, to_country, postcode, weight, length, width, height, value, partner_name):
        fedex_config = FedexConfig(
            key=settings.FEDEX_ACCOUNT_KEY[partner_name],
            password=settings.FEDEX_ACCOUNT_PASSWORD[partner_name],
            account_number=settings.FEDEX_ACCOUNT_NUMBER[partner_name],
            meter_number=settings.FEDEX_METER_NUMBER[partner_name],
            freight_account_number=settings.FEDEX_FREIGHT_ACCOUNT_NUMBER[partner_name])
        self.rate_request = FedexRateServiceRequest(fedex_config)
        self.country_code = to_country.iso_3166_1_a2
        self.weight = float(weight)
        self.width = width
        self.length = length
        self.height = height
        self.value = value
        self.postcode = postcode
        self.partner_name = partner_name

    def retrieveRates(self):
        shipping_options = []

        # This is very generalized, top-level information.
        # REGULAR_PICKUP, REQUEST_COURIER, DROP_BOX, BUSINESS_SERVICE_CENTER or STATION
        self.rate_request.RequestedShipment.DropoffType = 'REQUEST_COURIER'
        #make sure we don't deliver on weekend
        now = datetime.datetime.now()
        if now.isoweekday() in range(1, 6):
            self.rate_request.RequestedShipment.ShipTimestamp = now
        else:
            self.rate_request.RequestedShipment.ShipTimestamp = now + datetime.timedelta(2)
        # See page 355 in WS_ShipService.pdf for a full list. Here are the common ones:
        # STANDARD_OVERNIGHT, PRIORITY_OVERNIGHT, FEDEX_GROUND, FEDEX_EXPRESS_SAVER
        # To receive rates for multiple ServiceTypes set to None.
        self.rate_request.RequestedShipment.ServiceType = None

        # What kind of package this will be shipped in.
        # FEDEX_BOX, FEDEX_PAK, FEDEX_TUBE, YOUR_PACKAGING
        self.rate_request.RequestedShipment.PackagingType = 'YOUR_PACKAGING'

        # Shipper's address
        self.rate_request.RequestedShipment.Shipper.Address.PostalCode = '92705'
        self.rate_request.RequestedShipment.Shipper.Address.StateOrProvinceCode = 'CA'
        self.rate_request.RequestedShipment.Shipper.Address.CountryCode = 'US'
        self.rate_request.RequestedShipment.Shipper.Address.Residential = False

        # Recipient address
        self.rate_request.RequestedShipment.Recipient.Address.PostalCode = self.postcode
        self.rate_request.RequestedShipment.Recipient.Address.CountryCode = self.country_code
        # This is needed to ensure an accurate rate quote with the response.
        self.rate_request.RequestedShipment.Recipient.Address.Residential = True
        #include estimated duties and taxes in rate quote, can be ALL or NONE
        self.rate_request.RequestedShipment.EdtRequestType = 'ALL'

        # Who pays for the rate_request?
        # RECIPIENT, SENDER or THIRD_PARTY
        self.rate_request.RequestedShipment.ShippingChargesPayment.PaymentType = 'SENDER'

        package_weight = self.rate_request.create_wsdl_object_of_type('Weight')
        # Weight, in LB.
        package_weight.Value = self.weight
        package_weight.Units = "LB"

        package_dimensions = self.rate_request.create_wsdl_object_of_type('Dimensions')
        package_dimensions.Length = int(math.ceil(self.length))
        package_dimensions.Width = int(math.ceil(self.width))
        package_dimensions.Height = int(math.ceil(self.height))
        package_dimensions.Units.value = "IN"

        package = self.rate_request.create_wsdl_object_of_type('RequestedPackageLineItem')
        package.Weight = package_weight
        package.Dimensions = package_dimensions
        #declare contents value if its lower than $100 to get FedEx free insurance
        if self.value < 100:
            package.InsuredValue.Currency = 'USD'
            package.InsuredValue.Amount = self.value
        #package.Dimensions.Units = package1_dimensions_units
        #can be other values this is probably the most common
        package.PhysicalPackaging = 'BOX'
        # Required, but according to FedEx docs:
        # "Used only with PACKAGE_GROUPS, as a count of packages within a
        # group of identical packages". In practice you can use this to get rates
        # for a shipment with multiple packages of an identical package size/weight
        # on rate request without creating multiple RequestedPackageLineItem elements.
        # You can OPTIONALLY specify a package group:
        # package.GroupNumber = 0  # default is 0
        # The result will be found in RatedPackageDetail, with specified GroupNumber.
        package.GroupPackageCount = 1
        # Un-comment this to see the other variables you may set on a package.
        #print package

        # This adds the RequestedPackageLineItem WSDL object to the rate_request. It
        # increments the package count and total weight of the rate_request for you.
        self.rate_request.add_package(package)

        # If you'd like to see some documentation on the ship service WSDL, un-comment
        # this line. (Spammy).
        #print rate_request.client

        # Un-comment this to see your complete, ready-to-send request as it stands
        # before it is actually sent. This is useful for seeing what values you can
        # change.
        #print self.rate_request.RequestedShipment

        # Fires off the request, sets the 'response' attribute on the object.
        try:
            self.rate_request.send_request()
        except Exception:
            #log.critical("Fedex API error: %s, postal code: %s, country: %s" %
            #             (e, self.postcode, self.country_code))
            return shipping_options

        # This will show the reply to your rate_request being sent. You can access the
        # attributes throughgit status
        #  the response attribute on the request object. This is
        # good to un-comment to see the variables returned by the FedEx reply.
        #print rate_request.response

        # RateReplyDetails can contain rates for multiple ServiceTypes if ServiceType was set to None
        try:
            for service in self.rate_request.response.RateReplyDetails:
                #rate includes postage + surcharges
                rate = service.RatedShipmentDetails[0].ShipmentRateDetail.TotalNetFedExCharge.Amount
                #print service.RatedShipmentDetails[0].ShipmentRateDetail
                kwargs = {
                    'ship_charge_excl_revenue': D(str(rate)),
                    'service_code': service.ServiceType,
                    'country_code': self.country_code,
                    'contents_value': self.value
                }
                try:
                    shipping_option = FedEx(**kwargs)
                except ShippingMethodDoesNotExist:
                    continue

                surcharges = []

                for detail in service.RatedShipmentDetails:
                    #print detail.ShipmentRateDetail.Surcharges
                    for surcharge in detail.ShipmentRateDetail.Surcharges:
                        if surcharge.Description == 'On call pickup':
                            #dirty patch that removes the on call pickup surcharge for GLOBAL and PREFERRED
                            #- they have a free daily pickup
                            #and their FedEx account returns this surcharge accidentally
                            if self.partner_name not in [settings.GLOBAL, settings.PREFERRED]:
                                surcharges.append((surcharge.Description, surcharge.Amount.Amount))
                        else:
                            surcharges.append((surcharge.Description, surcharge.Amount.Amount))

                    shipping_option.add_surcharges(surcharges)
                shipping_options.append(shipping_option)
        except AttributeError:
            pass
            #log.critical("Fedex API response error: no RateReplyDetails found,"
            #             " postal code: %s, country: %s" % (self.postcode, self.country_code))
        return shipping_options


