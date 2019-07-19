from oscar.apps.checkout.calculators import OrderTotalCalculator as CoreOrderTotalCalculator
from oscar.core import prices


class OrderTotalCalculator(CoreOrderTotalCalculator):
    def calculate(self, basket, shipping_method, **kwargs):
        #we include shipping cost in basket, therefore we need to ignore the shipping_method
        #argument and set order total as basket total
        excl_tax = basket.total_excl_tax
        if basket.is_tax_known:
            incl_tax = basket.total_incl_tax
        else:
            incl_tax = None
        return prices.Price(
            currency=basket.currency,
            excl_tax=excl_tax, incl_tax=incl_tax)


