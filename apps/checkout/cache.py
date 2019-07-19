from django.core.cache import cache


def make_order_tracking_key(key):
    return "%s_%s" % ('order_tracking', key)


def store_order_tracking_value(key, val):
    if key:
        key = make_order_tracking_key(key)
        cache.set(key, val)

def get_order_tracking_value(key):
    data = None
    if key:
        key = make_order_tracking_key(key)
        data = cache.get(key)
    return data

def make_maxmind_key(key):
    return "%s_%s" % ('maxmind', key)


def store_maxmind_data(key, val):
    if key:
        key = make_maxmind_key(key)
        cache.set(key, val, timeout=60 * 60 * 24 * 30) #30 days

def get_maxmind_data(key):
    data = (None, None, None)
    if key:
        key = make_maxmind_key(key)
        data = cache.get(key, data)
    return data








