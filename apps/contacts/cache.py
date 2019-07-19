from django.core.cache import cache
import gdata.gauth

class GoogleTokenCache(object):
    @staticmethod
    def store_token(key, token):
        blob = gdata.gauth.token_to_blob(token)
        cache.set(key, blob, timeout=60*60*24*60)#60 days

    @staticmethod
    def get_token(key):
        blob = cache.get(key)
        if blob:
            return gdata.gauth.token_from_blob(blob)
        return None

    @staticmethod
    def delete_token(key):
        cache.delete(key)


