# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'BitcoinTransaction'
        db.create_table('bitcoin_bitcointransaction', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('raw_request', self.gf('django.db.models.fields.TextField')(max_length=512)),
            ('raw_response', self.gf('django.db.models.fields.TextField')(max_length=512)),
            ('response_time', self.gf('django.db.models.fields.FloatField')()),
            ('date_created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('is_sandbox', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('amount', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=12, decimal_places=2, blank=True)),
            ('amount_btc', self.gf('django.db.models.fields.DecimalField')(null=True, max_digits=12, decimal_places=8, blank=True)),
            ('currency', self.gf('django.db.models.fields.CharField')(max_length=32, null=True, blank=True)),
            ('token', self.gf('django.db.models.fields.CharField')(db_index=True, max_length=64, null=True, blank=True)),
            ('ack', self.gf('django.db.models.fields.CharField')(max_length=32)),
        ))
        db.send_create_signal('bitcoin', ['BitcoinTransaction'])

        # Adding model 'PaymentMessage'
        db.create_table('bitcoin_paymentmessage', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('raw_message', self.gf('django.db.models.fields.TextField')(max_length=512)),
            ('is_sandbox', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('transaction_id', self.gf('django.db.models.fields.CharField')(max_length=32, db_index=True)),
            ('date_created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
        ))
        db.send_create_signal('bitcoin', ['PaymentMessage'])


    def backwards(self, orm):
        # Deleting model 'BitcoinTransaction'
        db.delete_table('bitcoin_bitcointransaction')

        # Deleting model 'PaymentMessage'
        db.delete_table('bitcoin_paymentmessage')


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
            'token': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '64', 'null': 'True', 'blank': 'True'})
        },
        'bitcoin.paymentmessage': {
            'Meta': {'ordering': "('-date_created',)", 'object_name': 'PaymentMessage'},
            'date_created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_sandbox': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'raw_message': ('django.db.models.fields.TextField', [], {'max_length': '512'}),
            'transaction_id': ('django.db.models.fields.CharField', [], {'max_length': '32', 'db_index': 'True'})
        }
    }

    complete_apps = ['bitcoin']