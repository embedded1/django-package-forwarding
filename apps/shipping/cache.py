from django.core.cache import cache

PARTNER_CACHE_KEY = 'ACTIVE_PARTNER'
WAREHOUSE_ADDRESS_CACHE_KEY = 'WAREHOUSE_ADDRESS'
#PARTNER_CACHE_TIMEOUT = 60 * 60 * 24 * 30 #30 days

def store_active_partner(partner):
    cache.set(
        key=PARTNER_CACHE_KEY,
        value=partner)

def get_active_partner():
    return cache.get(key=PARTNER_CACHE_KEY)

def store_warehouse_address(addresses):
    cache.set(
        key=WAREHOUSE_ADDRESS_CACHE_KEY,
        value=addresses)

def get_warehouse_address():
    return cache.get(key=WAREHOUSE_ADDRESS_CACHE_KEY)


