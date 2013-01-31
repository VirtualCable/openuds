# encoding: utf-8
#@PydevCodeAnalysisIgnore
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):
    
    def forwards(self, orm):
        
        # Adding model 'Provider'
        db.create_table('uds_provider', (
            ('comments', self.gf('django.db.models.fields.CharField')(max_length=256)),
            ('data', self.gf('django.db.models.fields.TextField')(default='')),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('data_type', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=128)),
        ))
        db.send_create_signal('uds', ['Provider'])

        # Adding model 'Service'
        db.create_table('uds_service', (
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('data_type', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('comments', self.gf('django.db.models.fields.CharField')(max_length=256)),
            ('provider', self.gf('django.db.models.fields.related.ForeignKey')(related_name='services', to=orm['uds.Provider'])),
            ('data', self.gf('django.db.models.fields.TextField')(default='')),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('uds', ['Service'])

        # Adding unique constraint on 'Service', fields ['provider', 'name']
        db.create_unique('uds_service', ['provider_id', 'name'])

        # Adding model 'OSManager'
        db.create_table('uds_osmanager', (
            ('comments', self.gf('django.db.models.fields.CharField')(max_length=256)),
            ('data', self.gf('django.db.models.fields.TextField')(default='')),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('data_type', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=128)),
        ))
        db.send_create_signal('uds', ['OSManager'])

        # Adding model 'Transport'
        db.create_table('uds_transport', (
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=128)),
            ('data_type', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('comments', self.gf('django.db.models.fields.CharField')(max_length=256)),
            ('priority', self.gf('django.db.models.fields.IntegerField')(default=0, db_index=True)),
            ('nets_positive', self.gf('django.db.models.fields.BooleanField')(default=False, blank=True)),
            ('data', self.gf('django.db.models.fields.TextField')(default='')),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('uds', ['Transport'])

        # Adding model 'Authenticator'
        db.create_table('uds_authenticator', (
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=128)),
            ('data_type', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('comments', self.gf('django.db.models.fields.TextField')(default='')),
            ('priority', self.gf('django.db.models.fields.IntegerField')(default=0, db_index=True)),
            ('data', self.gf('django.db.models.fields.TextField')(default='')),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('uds', ['Authenticator'])

        # Adding model 'User'
        db.create_table('uds_user', (
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128, db_index=True)),
            ('staff_member', self.gf('django.db.models.fields.BooleanField')(default=False, blank=True)),
            ('manager', self.gf('django.db.models.fields.related.ForeignKey')(related_name='users', to=orm['uds.Authenticator'])),
            ('comments', self.gf('django.db.models.fields.CharField')(max_length=256)),
            ('real_name', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('state', self.gf('django.db.models.fields.CharField')(max_length=1, db_index=True)),
            ('is_admin', self.gf('django.db.models.fields.BooleanField')(default=False, blank=True)),
            ('last_access', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(1972, 7, 1, 0, 0))),
            ('password', self.gf('django.db.models.fields.CharField')(default='', max_length=128)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('uds', ['User'])

        # Adding unique constraint on 'User', fields ['manager', 'name']
        db.create_unique('uds_user', ['manager_id', 'name'])

        # Adding model 'Group'
        db.create_table('uds_group', (
            ('manager', self.gf('django.db.models.fields.related.ForeignKey')(related_name='groups', to=orm['uds.Authenticator'])),
            ('state', self.gf('django.db.models.fields.CharField')(default='A', max_length=1, db_index=True)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('comments', self.gf('django.db.models.fields.CharField')(default='', max_length=256)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128, db_index=True)),
        ))
        db.send_create_signal('uds', ['Group'])

        # Adding unique constraint on 'Group', fields ['manager', 'name']
        db.create_unique('uds_group', ['manager_id', 'name'])

        # Adding M2M table for field users on 'Group'
        db.create_table('uds_group_users', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('group', models.ForeignKey(orm['uds.group'], null=False)),
            ('user', models.ForeignKey(orm['uds.user'], null=False))
        ))
        db.create_unique('uds_group_users', ['group_id', 'user_id'])

        # Adding model 'UserPreference'
        db.create_table('uds_userpreference', (
            ('value', self.gf('django.db.models.fields.CharField')(max_length=128, db_index=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(related_name='preferences', to=orm['uds.User'])),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('module', self.gf('django.db.models.fields.CharField')(max_length=32, db_index=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=32, db_index=True)),
        ))
        db.send_create_signal('uds', ['UserPreference'])

        # Adding unique constraint on 'UserPreference', fields ['module', 'name']
        db.create_unique('uds_userpreference', ['module', 'name'])

        # Adding model 'DeployedService'
        db.create_table('uds__deployed_service', (
            ('initial_srvs', self.gf('django.db.models.fields.PositiveIntegerField')(default=0)),
            ('osmanager', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='deployedServices', null=True, to=orm['uds.OSManager'])),
            ('name', self.gf('django.db.models.fields.CharField')(default='', max_length=128)),
            ('service', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='deployedServices', null=True, to=orm['uds.Service'])),
            ('current_pub_revision', self.gf('django.db.models.fields.PositiveIntegerField')(default=1)),
            ('max_srvs', self.gf('django.db.models.fields.PositiveIntegerField')(default=0)),
            ('comments', self.gf('django.db.models.fields.CharField')(default='', max_length=256)),
            ('authenticator', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='deployedServices', null=True, to=orm['uds.Authenticator'])),
            ('state', self.gf('django.db.models.fields.CharField')(default='A', max_length=1, db_index=True)),
            ('cache_l2_srvs', self.gf('django.db.models.fields.PositiveIntegerField')(default=0)),
            ('cache_l1_srvs', self.gf('django.db.models.fields.PositiveIntegerField')(default=0)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('uds', ['DeployedService'])

        # Adding M2M table for field transports on 'DeployedService'
        db.create_table('uds__ds_trans', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('deployedservice', models.ForeignKey(orm['uds.deployedservice'], null=False)),
            ('transport', models.ForeignKey(orm['uds.transport'], null=False))
        ))
        db.create_unique('uds__ds_trans', ['deployedservice_id', 'transport_id'])

        # Adding M2M table for field assignedGroups on 'DeployedService'
        db.create_table('uds__ds_grps', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('deployedservice', models.ForeignKey(orm['uds.deployedservice'], null=False)),
            ('group', models.ForeignKey(orm['uds.group'], null=False))
        ))
        db.create_unique('uds__ds_grps', ['deployedservice_id', 'group_id'])

        # Adding model 'DeployedServicePublication'
        db.create_table('uds__deployed_service_pub', (
            ('deployed_service', self.gf('django.db.models.fields.related.ForeignKey')(related_name='publications', to=orm['uds.DeployedService'])),
            ('state', self.gf('django.db.models.fields.CharField')(default='P', max_length=1, db_index=True)),
            ('state_date', self.gf('django.db.models.fields.DateTimeField')()),
            ('publish_date', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('data', self.gf('django.db.models.fields.TextField')(default='')),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('revision', self.gf('django.db.models.fields.PositiveIntegerField')(default=1)),
        ))
        db.send_create_signal('uds', ['DeployedServicePublication'])

        # Adding model 'UserService'
        db.create_table('uds__user_service', (
            ('cache_level', self.gf('django.db.models.fields.PositiveSmallIntegerField')(default=0, db_index=True)),
            ('publication', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='userServices', null=True, to=orm['uds.DeployedServicePublication'])),
            ('in_use', self.gf('django.db.models.fields.BooleanField')(default=False, blank=True)),
            ('os_state', self.gf('django.db.models.fields.CharField')(default='P', max_length=1)),
            ('friendly_name', self.gf('django.db.models.fields.CharField')(default='', max_length=128)),
            ('deployed_service', self.gf('django.db.models.fields.related.ForeignKey')(related_name='userServices', to=orm['uds.DeployedService'])),
            ('creation_date', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('state', self.gf('django.db.models.fields.CharField')(default='P', max_length=1, db_index=True)),
            ('state_date', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('user', self.gf('django.db.models.fields.related.ForeignKey')(default=None, related_name='userServices', null=True, blank=True, to=orm['uds.User'])),
            ('in_use_date', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(1972, 7, 1, 0, 0))),
            ('data', self.gf('django.db.models.fields.TextField')(default='')),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('unique_id', self.gf('django.db.models.fields.CharField')(default='', max_length=128, db_index=True)),
        ))
        db.send_create_signal('uds', ['UserService'])

        # Adding model 'Cache'
        db.create_table('uds_utility_cache', (
            ('owner', self.gf('django.db.models.fields.CharField')(max_length=128, db_index=True)),
            ('validity', self.gf('django.db.models.fields.IntegerField')(default=60)),
            ('value', self.gf('django.db.models.fields.TextField')(default='')),
            ('key', self.gf('django.db.models.fields.CharField')(max_length=64, primary_key=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')()),
        ))
        db.send_create_signal('uds', ['Cache'])

        # Adding model 'Config'
        db.create_table('uds_configuration', (
            ('value', self.gf('django.db.models.fields.TextField')(default='')),
            ('section', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('key', self.gf('django.db.models.fields.CharField')(max_length=64)),
        ))
        db.send_create_signal('uds', ['Config'])

        # Adding unique constraint on 'Config', fields ['section', 'key']
        db.create_unique('uds_configuration', ['section', 'key'])

        # Adding model 'Storage'
        db.create_table('uds_storage', (
            ('owner', self.gf('django.db.models.fields.CharField')(max_length=128, db_index=True)),
            ('data', self.gf('django.db.models.fields.CharField')(default='', max_length=1024)),
            ('key', self.gf('django.db.models.fields.CharField')(max_length=64, primary_key=True)),
            ('attr1', self.gf('django.db.models.fields.CharField')(default=None, max_length=64, null=True, db_index=True, blank=True)),
        ))
        db.send_create_signal('uds', ['Storage'])

        # Adding model 'UniqueId'
        db.create_table('uds_uniqueid', (
            ('owner', self.gf('django.db.models.fields.CharField')(default='', max_length=128, db_index=True)),
            ('assigned', self.gf('django.db.models.fields.BooleanField')(default=True, db_index=True, blank=True)),
            ('basename', self.gf('django.db.models.fields.CharField')(max_length=32, db_index=True)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('seq', self.gf('django.db.models.fields.BigIntegerField')(db_index=True)),
        ))
        db.send_create_signal('uds', ['UniqueId'])

        # Adding unique constraint on 'UniqueId', fields ['basename', 'seq']
        db.create_unique('uds_uniqueid', ['basename', 'seq'])

        # Adding model 'Scheduler'
        db.create_table('uds_scheduler', (
            ('last_execution', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('frecuency', self.gf('django.db.models.fields.PositiveIntegerField')(default=86400)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('state', self.gf('django.db.models.fields.CharField')(default='X', max_length=1, db_index=True)),
            ('next_execution', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime(1972, 7, 1, 0, 0), db_index=True)),
            ('owner_server', self.gf('django.db.models.fields.CharField')(default='', max_length=64, db_index=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=64)),
        ))
        db.send_create_signal('uds', ['Scheduler'])

        # Adding model 'DelayedTask'
        db.create_table('uds_delayedtask', (
            ('insert_date', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('execution_delay', self.gf('django.db.models.fields.PositiveIntegerField')()),
            ('execution_time', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('instance', self.gf('django.db.models.fields.TextField')()),
            ('tag', self.gf('django.db.models.fields.CharField')(max_length=64, db_index=True)),
            ('type', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
        ))
        db.send_create_signal('uds', ['DelayedTask'])

        # Adding model 'Network'
        db.create_table('uds_network', (
            ('net_start', self.gf('django.db.models.fields.BigIntegerField')(db_index=True)),
            ('net_end', self.gf('django.db.models.fields.BigIntegerField')(db_index=True)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=64)),
        ))
        db.send_create_signal('uds', ['Network'])

        # Adding M2M table for field transports on 'Network'
        db.create_table('uds_net_trans', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('network', models.ForeignKey(orm['uds.network'], null=False)),
            ('transport', models.ForeignKey(orm['uds.transport'], null=False))
        ))
        db.create_unique('uds_net_trans', ['network_id', 'transport_id'])
    
    
    def backwards(self, orm):
        
        # Deleting model 'Provider'
        db.delete_table('uds_provider')

        # Deleting model 'Service'
        db.delete_table('uds_service')

        # Removing unique constraint on 'Service', fields ['provider', 'name']
        db.delete_unique('uds_service', ['provider_id', 'name'])

        # Deleting model 'OSManager'
        db.delete_table('uds_osmanager')

        # Deleting model 'Transport'
        db.delete_table('uds_transport')

        # Deleting model 'Authenticator'
        db.delete_table('uds_authenticator')

        # Deleting model 'User'
        db.delete_table('uds_user')

        # Removing unique constraint on 'User', fields ['manager', 'name']
        db.delete_unique('uds_user', ['manager_id', 'name'])

        # Deleting model 'Group'
        db.delete_table('uds_group')

        # Removing unique constraint on 'Group', fields ['manager', 'name']
        db.delete_unique('uds_group', ['manager_id', 'name'])

        # Removing M2M table for field users on 'Group'
        db.delete_table('uds_group_users')

        # Deleting model 'UserPreference'
        db.delete_table('uds_userpreference')

        # Removing unique constraint on 'UserPreference', fields ['module', 'name']
        db.delete_unique('uds_userpreference', ['module', 'name'])

        # Deleting model 'DeployedService'
        db.delete_table('uds__deployed_service')

        # Removing M2M table for field transports on 'DeployedService'
        db.delete_table('uds__ds_trans')

        # Removing M2M table for field assignedGroups on 'DeployedService'
        db.delete_table('uds__ds_grps')

        # Deleting model 'DeployedServicePublication'
        db.delete_table('uds__deployed_service_pub')

        # Deleting model 'UserService'
        db.delete_table('uds__user_service')

        # Deleting model 'Cache'
        db.delete_table('uds_utility_cache')

        # Deleting model 'Config'
        db.delete_table('uds_configuration')

        # Removing unique constraint on 'Config', fields ['section', 'key']
        db.delete_unique('uds_configuration', ['section', 'key'])

        # Deleting model 'Storage'
        db.delete_table('uds_storage')

        # Deleting model 'UniqueId'
        db.delete_table('uds_uniqueid')

        # Removing unique constraint on 'UniqueId', fields ['basename', 'seq']
        db.delete_unique('uds_uniqueid', ['basename', 'seq'])

        # Deleting model 'Scheduler'
        db.delete_table('uds_scheduler')

        # Deleting model 'DelayedTask'
        db.delete_table('uds_delayedtask')

        # Deleting model 'Network'
        db.delete_table('uds_network')

        # Removing M2M table for field transports on 'Network'
        db.delete_table('uds_net_trans')
    
    
    models = {
        'uds.authenticator': {
            'Meta': {'object_name': 'Authenticator'},
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
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
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
            'authenticator': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'deployedServices'", 'null': 'True', 'to': "orm['uds.Authenticator']"}),
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
            'transports': ('django.db.models.fields.related.ManyToManyField', [], {'related_name': "'deployedServices'", 'symmetrical': 'False', 'db_table': "'uds__ds_trans'", 'to': "orm['uds.Transport']"})
        },
        'uds.deployedservicepublication': {
            'Meta': {'object_name': 'DeployedServicePublication', 'db_table': "'uds__deployed_service_pub'"},
            'data': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'deployed_service': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'publications'", 'to': "orm['uds.DeployedService']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'publish_date': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'revision': ('django.db.models.fields.PositiveIntegerField', [], {'default': '1'}),
            'state': ('django.db.models.fields.CharField', [], {'default': "'P'", 'max_length': '1', 'db_index': 'True'}),
            'state_date': ('django.db.models.fields.DateTimeField', [], {})
        },
        'uds.group': {
            'Meta': {'unique_together': "(('manager', 'name'),)", 'object_name': 'Group'},
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
            'Meta': {'object_name': 'OSManager'},
            'comments': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'data': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'data_type': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '128'})
        },
        'uds.provider': {
            'Meta': {'object_name': 'Provider'},
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
            'Meta': {'unique_together': "(('provider', 'name'),)", 'object_name': 'Service'},
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
            'data': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '1024'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '64', 'primary_key': 'True'}),
            'owner': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'})
        },
        'uds.transport': {
            'Meta': {'object_name': 'Transport'},
            'comments': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'data': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'data_type': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '128'}),
            'nets_positive': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'priority': ('django.db.models.fields.IntegerField', [], {'default': '0', 'db_index': 'True'})
        },
        'uds.uniqueid': {
            'Meta': {'unique_together': "(('basename', 'seq'),)", 'object_name': 'UniqueId'},
            'assigned': ('django.db.models.fields.BooleanField', [], {'default': 'True', 'db_index': 'True', 'blank': 'True'}),
            'basename': ('django.db.models.fields.CharField', [], {'max_length': '32', 'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'owner': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '128', 'db_index': 'True'}),
            'seq': ('django.db.models.fields.BigIntegerField', [], {'db_index': 'True'})
        },
        'uds.user': {
            'Meta': {'unique_together': "(('manager', 'name'),)", 'object_name': 'User'},
            'comments': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_admin': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'last_access': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(1972, 7, 1, 0, 0)'}),
            'manager': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'users'", 'to': "orm['uds.Authenticator']"}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '128'}),
            'real_name': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'staff_member': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'state': ('django.db.models.fields.CharField', [], {'max_length': '1', 'db_index': 'True'})
        },
        'uds.userpreference': {
            'Meta': {'unique_together': "(('module', 'name'),)", 'object_name': 'UserPreference'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'module': ('django.db.models.fields.CharField', [], {'max_length': '32', 'db_index': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '32', 'db_index': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'preferences'", 'to': "orm['uds.User']"}),
            'value': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'})
        },
        'uds.userservice': {
            'Meta': {'object_name': 'UserService', 'db_table': "'uds__user_service'"},
            'cache_level': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '0', 'db_index': 'True'}),
            'creation_date': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'data': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'deployed_service': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'userServices'", 'to': "orm['uds.DeployedService']"}),
            'friendly_name': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '128'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'in_use': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'in_use_date': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime(1972, 7, 1, 0, 0)'}),
            'os_state': ('django.db.models.fields.CharField', [], {'default': "'P'", 'max_length': '1'}),
            'publication': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'userServices'", 'null': 'True', 'to': "orm['uds.DeployedServicePublication']"}),
            'state': ('django.db.models.fields.CharField', [], {'default': "'P'", 'max_length': '1', 'db_index': 'True'}),
            'state_date': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'unique_id': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '128', 'db_index': 'True'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'related_name': "'userServices'", 'null': 'True', 'blank': 'True', 'to': "orm['uds.User']"})
        }
    }
    
    complete_apps = ['uds']
