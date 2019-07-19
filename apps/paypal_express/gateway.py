from django.conf import settings
import logging
from paypal import gateway
from paypal import exceptions

# It's quite difficult to work out what the latest version of the PayPal
# Express API is.  The best way is to look for the 'web version: ...' string in
# the source of https://www.sandbox.paypal.com/
API_VERSION = getattr(settings, 'PAYPAL_API_VERSION', '88.0')

logger = logging.getLogger('paypal.AddressVerify')

def _fetch_response(extra_params):
    """
    Fetch the response from PayPal and return a transaction object
    """
    # Build parameter string
    params = {
        'METHOD': 'AddressVerify',
        'VERSION': API_VERSION,
        'USER': settings.PAYPAL_API_USERNAME,
        'PWD': settings.PAYPAL_API_PASSWORD,
        'SIGNATURE': settings.PAYPAL_API_SIGNATURE,
    }
    params.update(extra_params)

    if getattr(settings, 'PAYPAL_SANDBOX_MODE', True):
        url = 'https://api-3t.sandbox.paypal.com/nvp'
    else:
        url = 'https://api-3t.paypal.com/nvp'

    param_str = "\n".join(["%s: %s" % x for x in params.items()])
    logger.debug("Making AddressVerify request to %s with params:\n%s", url,
                 param_str)

    # Make HTTP request
    pairs = gateway.post(url, params)

    pairs_str = "\n".join(["%s: %s" % x for x in sorted(pairs.items())
                           if not x[0].startswith('_')])
    logger.debug("Response with params:\n%s", pairs_str)

    if 'Failure' in pairs['ACK']:
        msg = "Error %s - %s" % (pairs['L_ERRORCODE0'], pairs['L_LONGMESSAGE0'])
        logger.error(msg)
        raise exceptions.PayPalError(msg)

    try:
        confcode = pairs['CONFIRMATIONCODE']
    except KeyError:
        confcode = None

    try:
        street = pairs['STREETMATCH']
    except KeyError:
        street = None

    try:
        zip = pairs['ZIPMATCH']
    except KeyError:
        zip = None

    try:
        countrycode = pairs['COUNTRYCODE']
    except KeyError:
        countrycode = None

    return confcode, street, zip, countrycode


def address_txn(email, street, postcode):
    return _fetch_response({
        'EMAIL': email[:255],
        'STREET': street[:35],
        'ZIP': postcode[:16]
    })
