from django.contrib import admin
from django.db.models import get_model

AffiliatorAddress = get_model('address', 'AffiliatorAddress')


class AffiliatorAddressAdmin(admin.ModelAdmin):
    pass

admin.site.register(AffiliatorAddress, AffiliatorAddressAdmin)

import oscar.apps.address.admin


