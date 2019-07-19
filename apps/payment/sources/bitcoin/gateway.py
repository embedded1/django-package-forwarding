from django.conf import settings
from django.utils.http import urlencode
import simplejson as json
from . import models
from . import exceptions
from collections import OrderedDict
import requests
import time
import logging

logger = logging.getLogger('bitcoin')

def register_transaction(sender_email, sender_first_name,
                         sender_last_name, amount, basket_id, user_id):
    """
    Register the transaction with Bits of Gold and get the redirect URL
    """
    params = [
        ("amount", amount),
        ("email", sender_email),
        ("given_name", sender_first_name),
        ("family_name", sender_last_name),
        ("currency", "USD"),
        ("language", "EN"),
        ("userid", user_id),
        ("txid", basket_id)
    ]
    txn = _request(params)
    return txn.redirect_url, txn.token


def _request(params, headers=None, txn_fields=None):
    """
    Make a request to PayPal
    """
    msg = ''
    if headers is None:
        headers = {}
    if txn_fields is None:
        txn_fields = {}
    request_headers = {
        'Authorization': settings.BITS_OF_GOLD_SANDBOX_API_KEY if getattr(settings, 'BITS_OF_GOLD_SANDBOX_MODE', False)
            else settings.BITS_OF_GOLD_LIVE_API_KEY,
    }
    request_headers.update(headers)

    if getattr(settings, 'BITS_OF_GOLD_SANDBOX_MODE', False):
        url = 'http://sandbox.fundwithbitcoin.com/v1/payments'
        is_sandbox = True
    else:
        url = 'https://api.fundwithbitcoin.com/v1/payments'
        is_sandbox = False

    param_dict = OrderedDict(params)
    pairs = post(url, param_dict, request_headers)

    # Record transaction data - we save this model whether the txn
    # was successful or not
    txn = models.BitsOfGoldTransaction(
        is_sandbox=is_sandbox,
        raw_request=pairs['_raw_request'],
        raw_response=pairs['_raw_response'],
        response_time=pairs['_response_time'],
        currency='USD',
        token=pairs.get('token', None),
        ack=pairs.get('status', 'failed'),
        source=settings.BITS_OF_GOLD_LABEL,
        **txn_fields)

    txn.save()

    if not txn.is_successful:
        logger.error(msg)
        raise exceptions.BitsOfGoldError(msg)

    return txn


def post(url, params, headers=None):
    """
    Make a POST request to the URL using the key-value pairs.  Return
    a set of key-value pairs.

    :url: URL to post to
    :params: Dict of parameters to include in post payload
    :headers: Dict of headers
    """
    if headers is None:
        headers = {}
    if 'Content-type' not in headers:
        headers['Content-type'] = 'application/x-www-form-urlencoded'
    payload = urlencode(params)
    start_time = time.time()
    response = requests.post(
        url, payload,
        headers=headers)

    if response.status_code != requests.codes.ok:
        logger.error("BOG tran failed, payload = %s, status_code = %s", payload[:150], response.status_code)
        raise exceptions.BitsOfGoldError("An error occurred communicating with the Bitcoin processor")

    pairs = json.loads(response.content)
    # Add audit information
    pairs['_raw_request'] = payload
    pairs['_raw_response'] = urlencode(json.loads(response.content))
    pairs['_response_time'] = (time.time() - start_time) * 1000.0

    return pairs