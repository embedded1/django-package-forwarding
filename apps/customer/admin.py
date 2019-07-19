from django.contrib import admin
from django.db.models import get_model

CustomerFeedback = get_model('customer', 'CustomerFeedback')
admin.site.register(CustomerFeedback)

import oscar.apps.customer.admin


