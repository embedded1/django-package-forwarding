from apps.shipping import cache
from apps.partner.models import Partner
from django.conf import settings
import logging


logger = logging.getLogger("management_commands")


def get_warehouse_address(partner=None):
    """
    Return active partner primary address which is the warehouse address for
    receiving packages
    Currently we support only 1 active address
    """
    addresses = cache.get_warehouse_address()
    if not addresses:
        if partner is None:
            #search in cache
            partner = cache.get_active_partner()
            if not partner:
                #fallbacl to db
                partner = Partner.objects\
                    .get(name=settings.ACTIVE_PARTNER_NAME)
                cache.store_active_partner(partner)

        addresses = [partner.primary_address]
        cache.store_warehouse_address(addresses)
    return addresses