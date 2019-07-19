from django.contrib import admin
from django.db.models import get_model

Statistics = get_model('static', 'Statistics')

class StatisticsAdmin(admin.ModelAdmin):
    pass

admin.site.register(Statistics, StatisticsAdmin)