from django import template
from decimal import Decimal as D

register = template.Library()

@register.filter(name='total_basket_discounts')
def total_basket_discounts(basket):
    """
    get total basket discounts
    """
    total_discounts = 0

    offer_discounts = basket.offer_discounts
    voucher_discounts = basket.grouped_voucher_discounts

    for discount in offer_discounts:
        total_discounts += discount['discount']

    for voucher in voucher_discounts:
        total_discounts += voucher['discount']

    return total_discounts

@register.filter(name='total_order_discounts')
def total_order_discounts(order):
    """
    get total basket discounts
    """
    total_discounts = D('0.0')

    discounts = order.basket_discounts

    for discount in discounts:
        total_discounts += discount.amount

    return total_discounts
