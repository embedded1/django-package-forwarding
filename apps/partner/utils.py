from oscar.apps.partner.models import Partner, StockRecord
from django.conf import settings


def create_fee_stock_record(fee, charge):
    # STOCK RECORD
    partner, _ = Partner.objects.get_or_create(name='operations')
    record, created = StockRecord.objects.get_or_create(
        product=fee,
        partner=partner,
        defaults={
            'partner_sku': fee.upc,
            'num_in_stock': None,
            'price_excl_tax': charge
    })
    if not created:
        record.partner_sku = fee.upc
        record.num_in_stock = None
        record.price_excl_tax = charge
        record.save()

def get_partner_name(user):
    if user.is_staff:
        return settings.ACTIVE_PARTNER_NAME
    return user.partners.all()[0].name

def create_package_stock_record(package, user=None, partner=None):
    """
    Link package to partner
    """
    if partner is None:
        partner_name = get_partner_name(user)
        partner, _ = Partner.objects.get_or_create(name=partner_name)
    partner_sku = "%(code)s_%(upc)s" % {'code': partner.code, 'upc': package.upc}
    _, __ = StockRecord.objects.get_or_create(
        product=package,
        partner=partner,
        defaults={
            'partner_sku': partner_sku,
            'num_in_stock': None,
            'price_excl_tax': None
        })
    return partner
