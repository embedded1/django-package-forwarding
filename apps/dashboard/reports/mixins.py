from django.db.models import get_model

Product = get_model('catalogue', 'Product')
Order = get_model('order', 'Order')
Partner = get_model('partner', 'Partner')

class FilterPackageByPartner(object):
    def filter_by_partner(self):
        return  Product.packages.by_partner_user(self.user)

    def filter_in_store_packages_by_partner(self):
        return Product.in_store_packages.by_partner_user(self.user)


class FilterOrderByPartner(object):
    def filter_by_partner(self, partner_name=None):
        orders = Order.objects.all()
        if not self.user.is_staff:
            partners = list(Partner.objects.filter(users=self.user))
            orders = orders.filter(package__stockrecords__partner__in=partners)
        else:
            if partner_name:
                orders = orders.filter(package__stockrecords__partner__name=partner_name)
        return orders