from collections import namedtuple
from django.db import connections
from django.core.exceptions import ObjectDoesNotExist

def namedtuplefetchall(cursor):
    "Return all rows from a cursor as a namedtuple"
    desc = cursor.description
    nt_result = namedtuple('Result', [col[0] for col in desc])
    return [nt_result(*row) for row in cursor.fetchall()]


def find_shopify_store_id(store_name):
    store_name = store_name.strip().lower()
    cursor = connections['globalshipped'].cursor()
    levenshtein_tmpl = 'levenshtein(\'{0}\', "shop_authappshopuser"."store_name", 2, 0, 1)'.format(store_name)
    query = ('SELECT "shop_authappshopuser"."id", {0} FROM "shop_authappshopuser" '
             'WHERE soundex("shop_authappshopuser"."store_name") = soundex(\'{1}\') '
             'ORDER BY {2} LIMIT 1').format(levenshtein_tmpl, store_name, levenshtein_tmpl)
    cursor.execute(query)
    results = namedtuplefetchall(cursor)

    if len(results) == 0:
        raise ObjectDoesNotExist

    #we have exactly 1 result, let's check if the levenshtein distance is within range
    result = results[0]
    if result.levenshtein < 3:
        return result.id
    raise ObjectDoesNotExist



