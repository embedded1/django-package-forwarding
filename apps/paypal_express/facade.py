from apps.paypal_express.gateway import address_txn

def fetch_address_details(email, street, postcode):
    return address_txn(email, street, postcode)