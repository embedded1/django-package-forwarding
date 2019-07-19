# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'DealtasRedirect.last_visit_date'
        db.add_column('static_dealtasredirect', 'last_visit_date',
                      self.gf('django.db.models.fields.DateTimeField')(auto_now=True, default=datetime.datetime(2015, 7, 5, 0, 0), blank=True),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'DealtasRedirect.last_visit_date'
        db.delete_column('static_dealtasredirect', 'last_visit_date')


    models = {
        'static.dealtasredirect': {
            'Meta': {'object_name': 'DealtasRedirect'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip': ('django.db.models.fields.GenericIPAddressField', [], {'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'last_visit_date': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'visit_number': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '1'})
        }
    }

    complete_apps = ['static']