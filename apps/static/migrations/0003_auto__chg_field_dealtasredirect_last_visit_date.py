# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):

        # Changing field 'DealtasRedirect.last_visit_date'
        db.alter_column('static_dealtasredirect', 'last_visit_date', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, auto_now_add=True))

    def backwards(self, orm):

        # Changing field 'DealtasRedirect.last_visit_date'
        db.alter_column('static_dealtasredirect', 'last_visit_date', self.gf('django.db.models.fields.DateTimeField')(auto_now=True))

    models = {
        'static.dealtasredirect': {
            'Meta': {'object_name': 'DealtasRedirect'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip': ('django.db.models.fields.GenericIPAddressField', [], {'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'last_visit_date': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'auto_now_add': 'True', 'blank': 'True'}),
            'visit_number': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '1'})
        }
    }

    complete_apps = ['static']