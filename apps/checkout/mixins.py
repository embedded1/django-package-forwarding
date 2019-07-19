from oscar.apps.checkout.mixins import OrderPlacementMixin as CoreOrderPlacementMixin
from django.core.exceptions import ObjectDoesNotExist
from oscar.core.loading import get_model
from django.http import HttpResponseRedirect

UserAddress = get_model('address', 'UserAddress')


class OrderPlacementMixin(CoreOrderPlacementMixin):
    def update_address_book(self, user, shipping_addr):
        """
        extend Oscar functionality by setting the is_merchant attribute
        based on the data saved in session
        We don't save US addresses in address book as we don't allow shipments
        within the US anymore
        """
        is_merchant = self.checkout_session.is_merchant_address()
        if is_merchant or shipping_addr.country.iso_3166_1_a2 != 'US':
            try:
                user_addr = user.addresses.get(
                    hash=shipping_addr.generate_hash())
            except ObjectDoesNotExist:
                # Create a new user address
                user_addr = UserAddress(user=user)
                user_addr.is_merchant = is_merchant
                shipping_addr.populate_alternative_model(user_addr)
            user_addr.num_orders += 1
            user_addr.save()

    def place_order(self, order_number, user, basket, shipping_address,
                    shipping_method, total, billing_address=None, **kwargs):
        """
        We overwrite this function to pass the shipping surcharges and Google Analytics client ID down
        """
        surcharges_description_and_cost_cb = getattr(shipping_method, 'surcharges_description_and_cost', None)
        if surcharges_description_and_cost_cb:
            surcharges_description_and_cost = surcharges_description_and_cost_cb()
        else:
            surcharges_description_and_cost = None
        ga_client_id = kwargs.get('ga_client_id')
        return super(OrderPlacementMixin, self).place_order(
            order_number, user, basket,
            shipping_address, shipping_method, total, billing_address,
            shipping_surcharges=surcharges_description_and_cost,
            ga_client_id=ga_client_id,
            shipping_country=shipping_address.country.printable_name if shipping_address else 'United States')
