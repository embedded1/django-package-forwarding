import bottlenose
from lxml import objectify, etree
from amazon.api import AmazonProduct, LookupException, AsinNotFound

class AmazonCartApi(object):
    def __init__(self, aws_key, aws_secret, aws_associate_tag, region="US"):
          """Initialize an Amazon API Proxy.

          :param aws_key:
              A string representing an AWS authentication key.
          :param aws_secret:
              A string representing an AWS authentication secret.
          :param aws_associate_tag:
              A string representing an AWS associate tag.
          :param region:
              A string representing the region, defaulting to "US" (amazon.com)
              See keys of bottlenose.api.SERVICE_DOMAINS for options, which were
              CA, CN, DE, ES, FR, IT, JP, UK, US at the time of writing.
          """
          self.api = bottlenose.Amazon(
              aws_key, aws_secret, aws_associate_tag, Region=region)
          self.aws_associate_tag = aws_associate_tag
          self.region = region

    def CartCreate(self, **kwargs):
        response = self.api.CartCreate(**kwargs)

        root = objectify.fromstring(response)
        if root.Cart.Request.IsValid == 'False':
            code = root.Cart.Request.Errors.Error.Code
            msg = root.Cart.Request.Errors.Error.Message
            raise LookupException(
                "Amazon Product Lookup Error: '{0}', '{1}'".format(code, msg))
        if not hasattr(root.CartItems, 'CartItem'):
            raise AsinNotFound("ASIN(s) not found: '{0}'".format(
                etree.tostring(root, pretty_print=True)))
        if len(root.CartItems.CartItem) > 1:
            return [
                AmazonProduct(
                    item,
                    self.aws_associate_tag,
                    self,
                    region=self.region) for item in root.CartItems.CartItem
            ]
        else:
            return AmazonProduct(
                root.CartItems.CartItem,
                self.aws_associate_tag,
                self,
                region=self.region
            )
