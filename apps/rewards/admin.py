from django.contrib import admin
from django.db.models import get_model

LoyaltyReward = get_model('rewards', 'LoyaltyReward')
ReferralReward = get_model('rewards', 'ReferralReward')

admin.site.register(LoyaltyReward)
admin.site.register(ReferralReward)
