from django.core.cache import cache


class ProductCache(object):
    @staticmethod
    def store_product_status(key, status):
        cache.set(key, status, timeout=60*60*24*30)#30 days

    @staticmethod
    def get_product_status(key):
        return cache.get(key)

    @staticmethod
    def delete_product_status(key):
        cache.delete(key)





