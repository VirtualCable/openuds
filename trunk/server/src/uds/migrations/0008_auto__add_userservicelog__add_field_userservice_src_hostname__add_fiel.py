# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'UserServiceLog'
        db.create_table('uds__us_log', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('user_service', self.gf('django.db.models.fields.related.ForeignKey')(related_name='log', to=orm['uds.UserService'])),
            ('created', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, db_index=True, blank=True)),
            ('source', self.gf('django.db.models.fields.CharField')(default='internal', max_length=16, db_index=True)),
            ('level', self.gf('django.db.models.fields.PositiveSmallIntegerField')(default=0, db_index=True)),
            ('data', self.gf('django.db.models.fields.CharField')(default='', max_length=255)),
        ))
        db.send_create_signal('uds', ['UserServiceLog'])

        # Adding field 'UserService.src_hostname'
        db.add_column('uds__user_service', 'src_hostname',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=64),
                      keep_default=False)

        # Adding field 'UserService.src_ip'
        db.add_column('uds__user_service', 'src_ip',
                      self.gf('django.db.models.fields.CharField')(default='', max_length=15),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting model 'UserServiceLog'
        db.delete_table('uds__us_log')

        # Deleting field 'UserService.src_hostname'
        db.delete_column('uds__user_service', 'src_hostname')

        # Deleting field 'UserService.src_ip'
        db.delete_column('uds__user_service', 'src_ip')


    models = {
        'uds.authenticator': {
            'Meta': {'ordering': "('name',)", 'object_name': 'Authenticator'},
            'comments': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'data': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'data_type': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '128'}),
            'priority': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_index': 'True'})
        },
        'uds.cache': {
            'Meta': {'object_name': 'Cache', 'db_table': "'uds_utility_cache'"},
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '64', 'primary_key': 'True'}),
            'owner': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'validity': ('django.db.models.fields.IntegerField', [], {'default': '60'}),
            'value': ('django.db.models.fields.TextField', [], {'default': "''"})
        },
        'uds.config': {
            'Meta': {'unique_together': "(('section', 'key'),)", 'object_name': 'Config', 'db_table': "'uds_configuration'"},
            'crypt': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'long': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'section': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'value': ('django.db.models.fields.TextField', [], {'default': "''"})
        },
        'uds.delayedtask': {
            'Meta': {'object_name': 'DelayedTask'},
            'execution_delay': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'execution_time': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'insert_date': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'instance': ('django.db.models.fields.TextField', [], {}),
            'tag': ('django.db.models.fields.CharField', [], {'max_length': '64', 'db_index': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '128'})
        },
        'uds.deployedservice': {
            'Meta': {'object_name': 'DeployedService', 'db_table': "'uds__deployed_service'"},
            'assignedGroups': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'deployedServices'", 'symmetrical': 'False', 'db_table': "'uds__ds_grps'", 'to': "orm['uds.Group']"}),
            'cache_l1_srvs': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'cache_l2_srvs': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'comments': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '256'}),
            'current_pub_revision': ('django.db.models.fields.PositiveIntegerField', [], {'default': '1'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'initial_srvs': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'max_srvs': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '128'}),
            'osmanager': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'deployedServices'", 'null': 'True', 'to': "orm['uds.OSManager']"}),
            'service': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'deployedServices'", 'null': 'True', 'to': "orm['uds.Service']"}),
            'state': ('django.db.models.fields.CharField', [], {'default': "'A'", 'max_length': '1', 'db_index': 'True'}),
            'state_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(1972, 7, 1, 0, 0)'}),
            'transports': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'deployedServices'", 'symmetrical': 'False', 'db_table': "'uds__ds_trans'", 'to': "orm['uds.Transport']"})
        },
        'uds.deployedservicepublication': {
            'Meta': {'ordering': "('publish_date',)", 'object_name': 'DeployedServicePublication', 'db_table': "'uds__deployed_service_pub'"},
            'data': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'deployed_service': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'publications'", 'to': "orm['uds.DeployedService']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'publish_date': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'revision': ('django.db.models.fields.PositiveIntegerField', [], {'default': '1'}),
            'state': ('django.db.models.fields.CharField', [], {'default': "'P'", 'max_length': '1', 'db_index': 'True'}),
            'state_date': ('django.db.models.fields.DateTimeField', [], {})
        },
        'uds.group': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('manager', 'name'),)", 'object_name': 'Group'},
            'comments': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '256'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'manager': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'groups'", 'to': "orm['uds.Authenticator']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'state': ('django.db.models.fields.CharField', [], {'default': "'A'", 'max_length': '1', 'db_index': 'True'}),
            'users': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'groups'", 'symmetrical': 'False', 'to': "orm['uds.User']"})
        },
        'uds.network': {
            'Meta': {'object_name': 'Network'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '64'}),
            'net_end': ('django.db.models.fields.BigIntegerField', [], {'db_index': 'True'}),
            'net_start': ('django.db.models.fields.BigIntegerField', [], {'db_index': 'True'}),
            'transports': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'networks'", 'symmetrical': 'False', 'db_table': "'uds_net_trans'", 'to': "orm['uds.Transport']"})
        },
        'uds.osmanager': {
            'Meta': {'ordering': "('name',)", 'object_name': 'OSManager'},
            'comments': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'data': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'data_type': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '128'})
        },
        'uds.provider': {
            'Meta': {'ordering': "('name',)", 'object_name': 'Provider'},
            'comments': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'data': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'data_type': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '128'})
        },
        'uds.scheduler': {
            'Meta': {'object_name': 'Scheduler'},
            'frecuency': ('django.db.models.fields.PositiveIntegerField', [], {'default': '86400'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_execution': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '64'}),
            'next_execution': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(1972, 7, 1, 0, 0)', 'db_index': 'True'}),
            'owner_server': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '64', 'db_index': 'True'}),
            'state': ('django.db.models.fields.CharField', [], {'default': "'X'", 'max_length': '1', 'db_index': 'True'})
        },
        'uds.service': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('provider', 'name'),)", 'object_name': 'Service'},
            'comments': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'data': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'data_type': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'provider': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'services'", 'to': "orm['uds.Provider']"})
        },
        'uds.storage': {
            'Meta': {'object_name': 'Storage'},
            'attr1': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '64', 'null': 'True', 'db_index': 'True', 'blank': 'True'}),
            'data': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '64', 'primary_key': 'True'}),
            'owner': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'})
        },
        'uds.transport': {
            'Meta': {'ordering': "('name',)", 'object_name': 'Transport'},
            'comments': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'data': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'data_type': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '128'}),
            'nets_positive': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'priority': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_index': 'True'})
        },
        'uds.uniqueid': {
            'Meta': {'ordering': "('-seq',)", 'unique_together': "(('basename', 'seq'),)", 'object_name': 'UniqueId'},
            'assigned': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'db_index': 'True'}),
            'basename': ('django.db.models.fields.CharField', [], {'max_length': '32', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'owner': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '128', 'db_index': 'True'}),
            'seq': ('django.db.models.fields.BigIntegerField', [], {'db_index': 'True'})
        },
        'uds.user': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('manager', 'name'),)", 'object_name': 'User'},
            'comments': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_admin': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_access': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(1972, 7, 1, 0, 0)'}),
            'manager': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'users'", 'to': "orm['uds.Authenticator']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '128'}),
            'real_name': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'staff_member': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'state': ('django.db.models.fields.CharField', [], {'max_length': '1', 'db_index': 'True'})
        },
        'uds.userpreference': {
            'Meta': {'object_name': 'UserPreference'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'module': ('django.db.models.fields.CharField', [], {'max_length': '32', 'db_index': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '32', 'db_index': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'preferences'", 'to': "orm['uds.User']"}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'})
        },
        'uds.userservice': {
            'Meta': {'ordering': "('creation_date',)", 'object_name': 'UserService', 'db_table': "'uds__user_service'"},
            'cache_level': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '0', 'db_index': 'True'}),
            'creation_date': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'data': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'deployed_service': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'userServices'", 'to': "orm['uds.DeployedService']"}),
            'friendly_name': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '128'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'in_use': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'in_use_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(1972, 7, 1, 0, 0)'}),
            'os_state': ('django.db.models.fields.CharField', [], {'default': "'P'", 'max_length': '1'}),
            'publication': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'userServices'", 'null': 'True', 'to': "orm['uds.DeployedServicePublication']"}),
            'src_hostname': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '64'}),
            'src_ip': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '15'}),
            'state': ('django.db.models.fields.CharField', [], {'default': "'P'", 'max_length': '1', 'db_index': 'True'}),
            'state_date': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'unique_id': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '128', 'db_index': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "'userServices'", 'null': 'True', 'blank': 'True', 'to': "orm['uds.User']"})
        },
        'uds.userservicelog': {
            'Meta': {'object_name': 'UserServiceLog', 'db_table': "'uds__us_log'"},
            'created': ('django.db.models.fields.DateField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'data': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '255'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'level': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '0', 'db_index': 'True'}),
            'source': ('django.db.models.fields.CharField', [], {'default': "'internal'", 'max_length': '16', 'db_index': 'True'}),
            'user_service': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'log'", 'to': "orm['uds.UserService']"})
        }
    }

    complete_apps = ['uds']