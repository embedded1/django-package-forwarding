from django.contrib import admin
from . import models

class TxnAdmin(admin.ModelAdmin):
    list_display = ['token', 'amount', 'amount_btc', 'date_created']
    list_filter = ['token']
    readonly_fields = [
        'request',
        'response',
        'raw_request',
        'raw_response',
        'response_time',
        'date_created',
    ]


class PaymentMessageAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'date_created']
    list_filter = ['transaction_id']
    readonly_fields = [
        'is_sandbox',
        'transaction_id',
        'raw_message',
        'date_created',
    ]


admin.site.register(models.BitsOfGoldPaymentMessage, PaymentMessageAdmin)
admin.site.register(models.BitsOfGoldTransaction, TxnAdmin)