from django.db import models

class ProductManager(models.Manager):
    def get_query_set(self):
        """
        Return ``QuerySet`` with product_class content pre-loaded.
        """
        return super(ProductManager, self).get_query_set()\
            .select_related('product_class')

    def by_partner_user(self, user):
        """
        First we need to search for all packages,
        then return only packages related to this partner
        """
        if user.is_staff:
            return self.get_query_set()
        return self.get_query_set().filter(stockrecords__partner__users=user)

class PackageManager(ProductManager):
    def get_query_set(self):
        """
        Return all Packages
        """
        return super(PackageManager, self).get_query_set()\
            .filter(product_class__name='package')

    def by_partner_user(self, user):
        """
        First we need to search for all packages,
        then return only packages related to this partner
        """
        if user.is_staff:
            return self.get_query_set()
        return self.get_query_set().filter(stockrecords__partner__users=user)

class InStorePackageManager(PackageManager):
    def get_query_set(self):
        """
        Return all Packages not including packages that user requested to consolidate
        """
        return super(InStorePackageManager, self).get_query_set()\
            .filter(status__in=['pending', 'predefined_waiting_for_consolidation',
                                'waiting_for_consolidation', 'pre_pending',
                                'pending_returned_package'])

