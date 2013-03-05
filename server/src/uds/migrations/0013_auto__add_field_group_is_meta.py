# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'Group.is_meta'
        db.add_column(u'uds_group', 'is_meta',
                      self.gf('django.db.models.fields.BooleanField')(default=False, db_index=True),
                      keep_default=False)

        # Adding M2M table for field groups on 'Group'
        db.create_table(u'uds_group_groups', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('from_group', models.ForeignKey(orm[u'uds.group'], null=False)),
            ('to_group', models.ForeignKey(orm[u'uds.group'], null=False))
        ))
        db.create_unique(u'uds_group_groups', ['from_group_id', 'to_group_id'])


    def backwards(self, orm):
        # Deleting field 'Group.is_meta'
        db.delete_column(u'uds_group', 'is_meta')

        # Removing M2M table for field groups on 'Group'
        db.delete_table('uds_group_groups')


    models = {
        u'uds.authenticator': {
            'Meta': {'ordering': "(u'name',)", 'object_name': 'Authenticator'},
            'comments': ('django.db.models.fields.TextField', [], {'default': "u''"}),
            'data': ('django.db.models.fields.TextField', [], {'default': "u''"}),
            'data_type': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '128'}),
            'priority': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_index': 'True'}),
            'small_name': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '32', 'db_index': 'True'})
        },
        u'uds.cache': {
            'Meta': {'object_name': 'Cache', 'db_table': "u'uds_utility_cache'"},
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '64', 'primary_key': 'True'}),
            'owner': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'validity': ('django.db.models.fields.IntegerField', [], {'default': '60'}),
            'value': ('django.db.models.fields.TextField', [], {'default': "u''"})
        },
        u'uds.config': {
            'Meta': {'unique_together': "((u'section', u'key'),)", 'object_name': 'Config', 'db_table': "u'uds_configuration'"},
            'crypt': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '64', 'db_index': 'True'}),
            'long': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'section': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'value': ('django.db.models.fields.TextField', [], {'default': "u''"})
        },
        u'uds.delayedtask': {
            'Meta': {'object_name': 'DelayedTask'},
            'execution_delay': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'execution_time': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'insert_date': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'instance': ('django.db.models.fields.TextField', [], {}),
            'tag': ('django.db.models.fields.CharField', [], {'max_length': '64', 'db_index': 'True'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '128'})
        },
        u'uds.deployedservice': {
            'Meta': {'object_name': 'DeployedService', 'db_table': "u'uds__deployed_service'"},
            'assignedGroups': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "u'deployedServices'", 'symmetrical': 'False', 'db_table': "u'uds__ds_grps'", 'to': u"orm['uds.Group']"}),
            'cache_l1_srvs': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'cache_l2_srvs': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'comments': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '256'}),
            'current_pub_revision': ('django.db.models.fields.PositiveIntegerField', [], {'default': '1'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'initial_srvs': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'max_srvs': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'name': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '128'}),
            'osmanager': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "u'deployedServices'", 'null': 'True', 'to': u"orm['uds.OSManager']"}),
            'service': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "u'deployedServices'", 'null': 'True', 'to': u"orm['uds.Service']"}),
            'state': ('django.db.models.fields.CharField', [], {'default': "'A'", 'max_length': '1', 'db_index': 'True'}),
            'state_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(1972, 7, 1, 0, 0)'}),
            'transports': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "u'deployedServices'", 'symmetrical': 'False', 'db_table': "u'uds__ds_trans'", 'to': u"orm['uds.Transport']"})
        },
        u'uds.deployedservicepublication': {
            'Meta': {'ordering': "(u'publish_date',)", 'object_name': 'DeployedServicePublication', 'db_table': "u'uds__deployed_service_pub'"},
            'data': ('django.db.models.fields.TextField', [], {'default': "u''"}),
            'deployed_service': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'publications'", 'to': u"orm['uds.DeployedService']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'publish_date': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'revision': ('django.db.models.fields.PositiveIntegerField', [], {'default': '1'}),
            'state': ('django.db.models.fields.CharField', [], {'default': "'P'", 'max_length': '1', 'db_index': 'True'}),
            'state_date': ('django.db.models.fields.DateTimeField', [], {})
        },
        u'uds.group': {
            'Meta': {'ordering': "(u'name',)", 'unique_together': "((u'manager', u'name'),)", 'object_name': 'Group'},
            'comments': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '256'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['uds.Group']", 'symmetrical': 'False'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_meta': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'db_index': 'True'}),
            'manager': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'groups'", 'to': u"orm['uds.Authenticator']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'state': ('django.db.models.fields.CharField', [], {'default': "'A'", 'max_length': '1', 'db_index': 'True'}),
            'users': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "u'groups'", 'symmetrical': 'False', 'to': u"orm['uds.User']"})
        },
        u'uds.log': {
            'Meta': {'object_name': 'Log'},
            'created': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'data': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'level': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '0', 'db_index': 'True'}),
            'owner_id': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_index': 'True'}),
            'owner_type': ('django.db.models.fields.SmallIntegerField', [], {'default': '0', 'db_index': 'True'}),
            'source': ('django.db.models.fields.CharField', [], {'default': "u'internal'", 'max_length': '16', 'db_index': 'True'})
        },
        u'uds.network': {
            'Meta': {'object_name': 'Network'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '64'}),
            'net_end': ('django.db.models.fields.BigIntegerField', [], {'db_index': 'True'}),
            'net_start': ('django.db.models.fields.BigIntegerField', [], {'db_index': 'True'}),
            'transports': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "u'networks'", 'symmetrical': 'False', 'db_table': "u'uds_net_trans'", 'to': u"orm['uds.Transport']"})
        },
        u'uds.osmanager': {
            'Meta': {'ordering': "(u'name',)", 'object_name': 'OSManager'},
            'comments': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'data': ('django.db.models.fields.TextField', [], {'default': "u''"}),
            'data_type': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '128'})
        },
        u'uds.provider': {
            'Meta': {'ordering': "(u'name',)", 'object_name': 'Provider'},
            'comments': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'data': ('django.db.models.fields.TextField', [], {'default': "u''"}),
            'data_type': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '128'})
        },
        u'uds.scheduler': {
            'Meta': {'object_name': 'Scheduler'},
            'frecuency': ('django.db.models.fields.PositiveIntegerField', [], {'default': '86400'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'last_execution': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '64'}),
            'next_execution': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(1972, 7, 1, 0, 0)', 'db_index': 'True'}),
            'owner_server': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '64', 'db_index': 'True'}),
            'state': ('django.db.models.fields.CharField', [], {'default': "'X'", 'max_length': '1', 'db_index': 'True'})
        },
        u'uds.service': {
            'Meta': {'ordering': "(u'name',)", 'unique_together': "((u'provider', u'name'),)", 'object_name': 'Service'},
            'comments': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'data': ('django.db.models.fields.TextField', [], {'default': "u''"}),
            'data_type': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'provider': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'services'", 'to': u"orm['uds.Provider']"})
        },
        u'uds.statscounters': {
            'Meta': {'object_name': 'StatsCounters', 'db_table': "u'uds_stats_c'"},
            'counter_type': ('django.db.models.fields.SmallIntegerField', [], {'default': '0', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'owner_id': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_index': 'True'}),
            'owner_type': ('django.db.models.fields.SmallIntegerField', [], {'default': '0', 'db_index': 'True'}),
            'stamp': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_index': 'True'}),
            'value': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_index': 'True'})
        },
        u'uds.statsevents': {
            'Meta': {'object_name': 'StatsEvents', 'db_table': "u'uds_stats_e'"},
            'event_type': ('django.db.models.fields.SmallIntegerField', [], {'default': '0', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'owner_id': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_index': 'True'}),
            'owner_type': ('django.db.models.fields.SmallIntegerField', [], {'default': '0', 'db_index': 'True'}),
            'stamp': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_index': 'True'})
        },
        u'uds.storage': {
            'Meta': {'object_name': 'Storage'},
            'attr1': ('django.db.models.fields.CharField', [], {'default': 'None', 'max_length': '64', 'null': 'True', 'db_index': 'True', 'blank': 'True'}),
            'data': ('django.db.models.fields.TextField', [], {'default': "u''"}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '64', 'primary_key': 'True'}),
            'owner': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'})
        },
        u'uds.transport': {
            'Meta': {'ordering': "(u'name',)", 'object_name': 'Transport'},
            'comments': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'data': ('django.db.models.fields.TextField', [], {'default': "u''"}),
            'data_type': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '128'}),
            'nets_positive': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'priority': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_index': 'True'})
        },
        u'uds.uniqueid': {
            'Meta': {'ordering': "(u'-seq',)", 'unique_together': "((u'basename', u'seq'),)", 'object_name': 'UniqueId'},
            'assigned': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'db_index': 'True'}),
            'basename': ('django.db.models.fields.CharField', [], {'max_length': '32', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'owner': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '128', 'db_index': 'True'}),
            'seq': ('django.db.models.fields.BigIntegerField', [], {'db_index': 'True'})
        },
        u'uds.user': {
            'Meta': {'ordering': "(u'name',)", 'unique_together': "((u'manager', u'name'),)", 'object_name': 'User'},
            'comments': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_admin': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_access': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(1972, 7, 1, 0, 0)'}),
            'manager': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'users'", 'to': u"orm['uds.Authenticator']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '128'}),
            'real_name': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'staff_member': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'state': ('django.db.models.fields.CharField', [], {'max_length': '1', 'db_index': 'True'})
        },
        u'uds.userpreference': {
            'Meta': {'object_name': 'UserPreference'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'module': ('django.db.models.fields.CharField', [], {'max_length': '32', 'db_index': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '32', 'db_index': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'preferences'", 'to': u"orm['uds.User']"}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'})
        },
        u'uds.userservice': {
            'Meta': {'ordering': "(u'creation_date',)", 'object_name': 'UserService', 'db_table': "u'uds__user_service'"},
            'cache_level': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '0', 'db_index': 'True'}),
            'creation_date': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'data': ('django.db.models.fields.TextField', [], {'default': "u''"}),
            'deployed_service': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'userServices'", 'to': u"orm['uds.DeployedService']"}),
            'friendly_name': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '128'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'in_use': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'in_use_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(1972, 7, 1, 0, 0)'}),
            'os_state': ('django.db.models.fields.CharField', [], {'default': "'P'", 'max_length': '1'}),
            'publication': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "u'userServices'", 'null': 'True', 'to': u"orm['uds.DeployedServicePublication']"}),
            'src_hostname': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '64'}),
            'src_ip': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '15'}),
            'state': ('django.db.models.fields.CharField', [], {'default': "'P'", 'max_length': '1', 'db_index': 'True'}),
            'state_date': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'db_index': 'True', 'blank': 'True'}),
            'unique_id': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '128', 'db_index': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "u'userServices'", 'null': 'True', 'blank': 'True', 'to': u"orm['uds.User']"})
        }
    }

    complete_apps = ['uds']