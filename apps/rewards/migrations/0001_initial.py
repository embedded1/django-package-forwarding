# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'LoyaltyReward'
        db.create_table('rewards_loyaltyreward', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('profile', self.gf('django.db.models.fields.related.ForeignKey')(related_name='rewards_loyaltyreward_related', to=orm['user.Profile'])),
            ('amount', self.gf('django.db.models.fields.DecimalField')(max_digits=10, decimal_places=2)),
            ('date_credited', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('date_redeemed', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('is_active', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('type', self.gf('django.db.models.fields.CharField')(max_length=64)),
        ))
        db.send_create_signal('rewards', ['LoyaltyReward'])

        # Adding model 'ReferralReward'
        db.create_table('rewards_referralreward', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('profile', self.gf('django.db.models.fields.related.ForeignKey')(related_name='rewards_referralreward_related', to=orm['user.Profile'])),
            ('amount', self.gf('django.db.models.fields.DecimalField')(max_digits=10, decimal_places=2)),
            ('date_credited', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('date_redeemed', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('is_active', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('type', self.gf('django.db.models.fields.CharField')(max_length=64)),
        ))
        db.send_create_signal('rewards', ['ReferralReward'])

        # Adding model 'AffiliateReward'
        db.create_table('rewards_affiliatereward', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('profile', self.gf('django.db.models.fields.related.ForeignKey')(related_name='rewards_affiliatereward_related', to=orm['user.Profile'])),
            ('amount', self.gf('django.db.models.fields.DecimalField')(max_digits=10, decimal_places=2)),
            ('date_credited', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('date_redeemed', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
            ('is_active', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('type', self.gf('django.db.models.fields.CharField')(max_length=64)),
        ))
        db.send_create_signal('rewards', ['AffiliateReward'])

        # Adding model 'CreditBenefit'
        db.create_table('rewards_creditbenefit', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('description', self.gf('django.db.models.fields.CharField')(max_length=64)),
        ))
        db.send_create_signal('rewards', ['CreditBenefit'])


    def backwards(self, orm):
        # Deleting model 'LoyaltyReward'
        db.delete_table('rewards_loyaltyreward')

        # Deleting model 'ReferralReward'
        db.delete_table('rewards_referralreward')

        # Deleting model 'AffiliateReward'
        db.delete_table('rewards_affiliatereward')

        # Deleting model 'CreditBenefit'
        db.delete_table('rewards_creditbenefit')


    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "('content_type__app_label', 'content_type__model', 'codename')", 'unique_together': "(('content_type', 'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'referrals.referral': {
            'Meta': {'object_name': 'Referral'},
            'code': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '40'}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'expired_at': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'label': ('django.db.models.fields.CharField', [], {'max_length': '100', 'blank': 'True'}),
            'redirect_to': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'target_content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']", 'null': 'True', 'blank': 'True'}),
            'target_object_id': ('django.db.models.fields.PositiveIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'referral_codes'", 'null': 'True', 'to': "orm['auth.User']"})
        },
        'rewards.affiliatereward': {
            'Meta': {'object_name': 'AffiliateReward'},
            'amount': ('django.db.models.fields.DecimalField', [], {'max_digits': '10', 'decimal_places': '2'}),
            'date_credited': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_redeemed': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'profile': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'rewards_affiliatereward_related'", 'to': "orm['user.Profile']"}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '64'})
        },
        'rewards.creditbenefit': {
            'Meta': {'object_name': 'CreditBenefit'},
            'description': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'rewards.loyaltyreward': {
            'Meta': {'object_name': 'LoyaltyReward'},
            'amount': ('django.db.models.fields.DecimalField', [], {'max_digits': '10', 'decimal_places': '2'}),
            'date_credited': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_redeemed': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'profile': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'rewards_loyaltyreward_related'", 'to': "orm['user.Profile']"}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '64'})
        },
        'rewards.referralreward': {
            'Meta': {'object_name': 'ReferralReward'},
            'amount': ('django.db.models.fields.DecimalField', [], {'max_digits': '10', 'decimal_places': '2'}),
            'date_credited': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'date_redeemed': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'profile': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'rewards_referralreward_related'", 'to': "orm['user.Profile']"}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '64'})
        },
        'user.profile': {
            'Meta': {'object_name': 'Profile'},
            'city': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'country': ('django.db.models.fields.CharField', [], {'max_length': '3', 'null': 'True', 'blank': 'True'}),
            'custom_requests_details': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'custom_requests_done': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            'email_confirmed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'express_checkout_done': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'extra_protection_done': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            'filling_customs_declaration_done': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip': ('django.db.models.fields.GenericIPAddressField', [], {'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'is_consolidate_every_new_package': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_custom_requests': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'is_express_checkout': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'is_extra_protection': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'is_filling_customs_declaration': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_photos': ('django.db.models.fields.CharField', [], {'default': "'Zero'", 'max_length': '16'}),
            'is_remove_invoice': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'is_repackaging': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'package_tracking': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'photos_done': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'proxy_score': ('django.db.models.fields.DecimalField', [], {'null': 'True', 'max_digits': '5', 'decimal_places': '2', 'blank': 'True'}),
            'referral': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['referrals.Referral']", 'unique': 'True', 'null': 'True', 'blank': 'True'}),
            'remove_invoice_done': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            'repackaging_done': ('django.db.models.fields.NullBooleanField', [], {'null': 'True', 'blank': 'True'}),
            'short_referral_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'skip_pp_verified_account_test': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'tour_end_step': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
            'tour_started': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'user': ('django.db.models.fields.related.OneToOneField', [], {'related_name': "'profile'", 'unique': 'True', 'to': "orm['auth.User']"}),
            'uuid': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '64', 'db_index': 'True'})
        }
    }

    complete_apps = ['rewards']