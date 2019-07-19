# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Deleting field 'PaymentMessage.label'
        db.delete_column('bitcoin_paymentmessage', 'label')

        # Adding field 'PaymentMessage.source'
        db.add_column('bitcoin_paymentmessage', 'source',
                      self.gf('django.db.models.fields.CharField')(default='BitcoinPay', max_length=32, db_index=True),
                      keep_default=False)

        # Deleting field 'BitcoinTransaction.label'
        db.delete_column('bitcoin_bitcointransaction', 'label')

        # Adding field 'BitcoinTransaction.source'
        db.add_column('bitcoin_bitcointransaction', 'source',
                      self.gf('django.db.models.fields.CharField')(default='BitcoinPay', max_length=32, db_index=True),
                      keep_default=False)


    def backwards(self, orm):

        # User chose to not deal with backwards NULL issues for 'PaymentMessage.label'
        raise RuntimeError("Cannot reverse this migration. 'PaymentMessage.label' and its values cannot be restored.")
        
        # The following code is provided here to aid in writing a correct migration        # Adding field 'PaymentMessage.label'
        db.add_column('bitcoin_paymentmessage', 'label',
                      self.gf('django.db.models.fields.CharField')(max_length=32, db_index=True),
                      keep_default=False)

        # Deleting field 'PaymentMessage.source'
        db.delete_column('bitcoin_paymentmessage', 'source')


        # User chose to not deal with backwards NULL issues for 'BitcoinTransaction.label'
        raise RuntimeError("Cannot reverse this migration. 'BitcoinTransaction.label' and its values cannot be restored.")
        
        # The following code is provided here to aid in writing a correct migration        # Adding field 'BitcoinTransaction.label'
        db.add_column('bitcoin_bitcointransaction', 'label',
                      self.gf('django.db.models.fields.CharField')(max_length=32, db_index=True),
                      keep_default=False)

        # Deleting field 'BitcoinTransaction.source'
        db.delete_column('bitcoin_bitcointransaction', 'source')


    models = {
        'bitcoin.bitcointransaction': {
            'Meta': {'ordering': "('-date_created',)", 'object_name': 'BitcoinTransaction'},
            'ack': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'amount': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '12', 'decimal_places': '2', 'blank': 'True'}),
            'amount_btc': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '12', 'decimal_places': '8', 'blank': 'True'}),
            'currency': ('django.db.models.fields.CharField', [], {'max_length': '32', 'null': 'True', 'blank': 'True'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_sandbox': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'raw_request': ('django.db.models.fields.TextField', [], {'max_length': '512'}),
            'raw_response': ('django.db.models.fields.TextField', [], {'max_length': '512'}),
            'response_time': ('django.db.models.fields.FloatField', [], {}),
            'source': ('django.db.models.fields.CharField', [], {'max_length': '32', 'db_index': 'True'}),
            'token': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '64', 'null': 'True', 'blank': 'True'})
        },
        'bitcoin.paymentmessage': {
            'Meta': {'ordering': "('-date_created',)", 'object_name': 'PaymentMessage'},
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_sandbox': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'payment_status': ('django.db.models.fields.CharField', [], {'max_length': '32', 'db_index': 'True'}),
            'raw_message': ('django.db.models.fields.TextField', [], {'max_length': '512'}),
            'source': ('django.db.models.fields.CharField', [], {'max_length': '32', 'db_index': 'True'}),
            'transaction_id': ('django.db.models.fields.CharField', [], {'max_length': '32', 'db_index': 'True'})
        }
    }

    complete_apps = ['bitcoin']