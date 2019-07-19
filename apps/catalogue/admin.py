from django.contrib import admin
from .models import (
    ProductCustomsForm, CustomsFormItem,
    ProductSpecialRequests, ProductConsolidationRequests,
    AdditionalPackageReceiver, PackageReceiverDocument,
    PackageLocation)


class CustomsFormAdmin(admin.ModelAdmin):
    pass

class CustomsFormItemAdmin(admin.ModelAdmin):
    pass

class ProductSpecialRequestsAdmin(admin.ModelAdmin):
    pass

class ProductConsolidationRequestsAdmin(admin.ModelAdmin):
    pass

class AdditionalPackageReceiverAdmin(admin.ModelAdmin):
    pass

class PackageReceiverDocumentAdmin(admin.ModelAdmin):
    pass

class PackageLocationAdmin(admin.ModelAdmin):
    pass

admin.site.register(ProductCustomsForm, CustomsFormAdmin)
admin.site.register(CustomsFormItem, CustomsFormItemAdmin)
admin.site.register(ProductSpecialRequests, ProductSpecialRequestsAdmin)
admin.site.register(ProductConsolidationRequests, ProductConsolidationRequestsAdmin)
admin.site.register(AdditionalPackageReceiver, AdditionalPackageReceiverAdmin)
admin.site.register(PackageReceiverDocument, PackageReceiverDocumentAdmin)
admin.site.register(PackageLocation, PackageLocationAdmin)

import oscar.apps.catalogue.admin
