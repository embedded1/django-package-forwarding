# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Statistics'
        db.create_table('static_statistics', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=32)),
            ('usage_counter', self.gf('django.db.models.fields.BigIntegerField')(default=0)),
        ))
        db.send_create_signal('static', ['Statistics'])


    def backwards(self, orm):
        # Deleting model 'Statistics'
        db.delete_table('static_statistics')


    models = {
        'static.dealtasredirect': {
            'Meta': {'object_name': 'DealtasRedirect'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip': ('django.db.models.fields.GenericIPAddressField', [], {'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'last_visit_date': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'visit_number': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '1'})
        },
        'static.statistics': {
            'Meta': {'object_name': 'Statistics'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'usage_counter': ('django.db.models.fields.BigIntegerField', [], {'default': '0'})
        }
    }

    complete_apps = ['static']