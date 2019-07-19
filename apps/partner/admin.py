from django.contrib import admin
from django.db.models import get_model

admin.site.register(get_model('partner', 'PartnerAddress'))
admin.site.register(get_model('partner', 'PartnerOrderPaymentSettings'))


import oscar.apps.partner.admin
