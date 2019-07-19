from django.conf import settings
from django.utils.http import urlencode
import simplejson as json
from django.core.urlresolvers import reverse
from apps.payment.sources.bitcoinpay import models
from . import exceptions
import requests
import time
import logging

logger = logging.getLogger('bitcoin')

def register_transaction(sender_email, amount, basket_id, user_id, **kwargs):
    """
    Register the transaction with Bitcoinpay and get the redirect URL
    """
    params = {
        "price": amount,
        "currency": "USD",
        "settled_currency": "USD",
        "notify_url": 'https://9c0c60e2.ngrok.io%s' % reverse('webhooks:bitcoinpay-ipn') if settings.DEBUG else
                      'https://usendhome.com%s' % reverse('webhooks:bitcoinpay-ipn'),
        "return_url": 'https://usendhome.com%s' % reverse('bitcoinpay-success-response',
                                                          kwargs={'basket_id': basket_id})
    }
    reference = {'email': sender_email, 'txid': basket_id}
    params['reference'] = json.dumps(reference)
    txn = _request(params)
    return txn.redirect_url, txn.token


def _request(params, headers=None, txn_fields=None):
    """
    Make a request to PayPal
    """
    if headers is None:
        headers = {}
    if txn_fields is None:
        txn_fields = {}
    request_headers = {'Authorization': 'Token {}'.format(settings.BITCOIN_PAY_LIVE_API_KEY)}
    request_headers.update(headers)

    url = 'https://bitcoinpay.com/api/v1/payment/btc'
    pairs = post(url, params, request_headers)

    # Record transaction data - we save this model whether the txn
    # was successful or not
    txn = models.BitcoinPayTransaction(
        is_sandbox=False,
        raw_request=pairs['_raw_request'],
        raw_response=pairs['_raw_response'],
        response_time=pairs['_response_time'],
        currency=pairs.get('currency', 'USD'),
        token=pairs.get('payment_id'),
        ack=pairs.get('status', 'invalid'),
        amount=pairs.get('price', 0),
        source=settings.BITCOIN_PAY_LABEL,
        **txn_fields)

    txn.save()
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
        headers['Content-type'] = 'application/json'
    payload = json.dumps(params)
    start_time = time.time()
    response = requests.post(
        url, payload,
        headers=headers)

    if response.status_code != requests.codes.ok:
        logger.error("BitcoinPay tran failed, payload = %s, status_code = %s", payload[:150], response.status_code)
        raise exceptions.BitcoinPayError("An error occurred communicating with the Bitcoin processor")

    content = json.loads(response.content)
    pairs = content['data']
    # Add audit information
    pairs['_raw_request'] = urlencode(params)
    pairs['_raw_response'] = urlencode(content['data'])
    pairs['_response_time'] = (time.time() - start_time) * 1000.0

    return pairs