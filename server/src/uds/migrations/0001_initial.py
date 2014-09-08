# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Authenticator',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=128)),
                ('data_type', models.CharField(max_length=128)),
                ('data', models.TextField(default='')),
                ('comments', models.TextField(default='')),
                ('priority', models.IntegerField(default=0, db_index=True)),
                ('small_name', models.CharField(default='', max_length=32, db_index=True)),
            ],
            options={
                'ordering': ('name',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Cache',
            fields=[
                ('owner', models.CharField(max_length=128, db_index=True)),
                ('key', models.CharField(max_length=64, serialize=False, primary_key=True)),
                ('value', models.TextField(default='')),
                ('created', models.DateTimeField()),
                ('validity', models.IntegerField(default=60)),
            ],
            options={
                'db_table': 'uds_utility_cache',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Config',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('section', models.CharField(max_length=128, db_index=True)),
                ('key', models.CharField(max_length=64, db_index=True)),
                ('value', models.TextField(default='')),
                ('crypt', models.BooleanField(default=False)),
                ('long', models.BooleanField(default=False)),
                ('field_type', models.IntegerField(default=-1)),
            ],
            options={
                'db_table': 'uds_configuration',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='DelayedTask',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('type', models.CharField(max_length=128)),
                ('tag', models.CharField(max_length=64, db_index=True)),
                ('instance', models.TextField()),
                ('insert_date', models.DateTimeField(auto_now_add=True)),
                ('execution_delay', models.PositiveIntegerField()),
                ('execution_time', models.DateTimeField(db_index=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='DeployedService',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(default='', max_length=128)),
                ('comments', models.CharField(default='', max_length=256)),
                ('state', models.CharField(default='A', max_length=1, db_index=True)),
                ('state_date', models.DateTimeField(default=datetime.datetime(1972, 7, 1, 0, 0))),
                ('initial_srvs', models.PositiveIntegerField(default=0)),
                ('cache_l1_srvs', models.PositiveIntegerField(default=0)),
                ('cache_l2_srvs', models.PositiveIntegerField(default=0)),
                ('max_srvs', models.PositiveIntegerField(default=0)),
                ('current_pub_revision', models.PositiveIntegerField(default=1)),
            ],
            options={
                'db_table': 'uds__deployed_service',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='DeployedServicePublication',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('publish_date', models.DateTimeField(db_index=True)),
                ('data', models.TextField(default='')),
                ('state', models.CharField(default='P', max_length=1, db_index=True)),
                ('state_date', models.DateTimeField()),
                ('revision', models.PositiveIntegerField(default=1)),
                ('deployed_service', models.ForeignKey(related_name='publications', to='uds.DeployedService')),
            ],
            options={
                'ordering': ('publish_date',),
                'db_table': 'uds__deployed_service_pub',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Group',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, db_index=True)),
                ('state', models.CharField(default='A', max_length=1, db_index=True)),
                ('comments', models.CharField(default='', max_length=256)),
                ('is_meta', models.BooleanField(default=False, db_index=True)),
                ('meta_if_any', models.BooleanField(default=False)),
                ('groups', models.ManyToManyField(to='uds.Group')),
                ('manager', models.ForeignKey(related_name='groups', to='uds.Authenticator')),
            ],
            options={
                'ordering': ('name',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Log',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('owner_id', models.IntegerField(default=0, db_index=True)),
                ('owner_type', models.SmallIntegerField(default=0, db_index=True)),
                ('created', models.DateTimeField(db_index=True)),
                ('source', models.CharField(default='internal', max_length=16, db_index=True)),
                ('level', models.PositiveSmallIntegerField(default=0, db_index=True)),
                ('data', models.CharField(default='', max_length=255)),
            ],
            options={
                'db_table': 'uds_log',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Network',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=64)),
                ('net_start', models.BigIntegerField(db_index=True)),
                ('net_end', models.BigIntegerField(db_index=True)),
                ('net_string', models.CharField(default='', max_length=128)),
            ],
            options={
                'ordering': ('name',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='OSManager',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=128)),
                ('data_type', models.CharField(max_length=128)),
                ('data', models.TextField(default='')),
                ('comments', models.CharField(max_length=256)),
            ],
            options={
                'ordering': ('name',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Provider',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=128)),
                ('data_type', models.CharField(max_length=128)),
                ('data', models.TextField(default='')),
                ('comments', models.CharField(max_length=256)),
            ],
            options={
                'ordering': ('name',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Scheduler',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=64)),
                ('frecuency', models.PositiveIntegerField(default=86400)),
                ('last_execution', models.DateTimeField(auto_now_add=True)),
                ('next_execution', models.DateTimeField(default=datetime.datetime(1972, 7, 1, 0, 0), db_index=True)),
                ('owner_server', models.CharField(default='', max_length=64, db_index=True)),
                ('state', models.CharField(default='X', max_length=1, db_index=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Service',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128)),
                ('data_type', models.CharField(max_length=128)),
                ('data', models.TextField(default='')),
                ('comments', models.CharField(max_length=256)),
                ('provider', models.ForeignKey(related_name='services', to='uds.Provider')),
            ],
            options={
                'ordering': ('name',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='StatsCounters',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('owner_id', models.IntegerField(default=0, db_index=True)),
                ('owner_type', models.SmallIntegerField(default=0, db_index=True)),
                ('counter_type', models.SmallIntegerField(default=0, db_index=True)),
                ('stamp', models.IntegerField(default=0, db_index=True)),
                ('value', models.IntegerField(default=0, db_index=True)),
            ],
            options={
                'db_table': 'uds_stats_c',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='StatsEvents',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('owner_id', models.IntegerField(default=0, db_index=True)),
                ('owner_type', models.SmallIntegerField(default=0, db_index=True)),
                ('event_type', models.SmallIntegerField(default=0, db_index=True)),
                ('stamp', models.IntegerField(default=0, db_index=True)),
            ],
            options={
                'db_table': 'uds_stats_e',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Storage',
            fields=[
                ('owner', models.CharField(max_length=128, db_index=True)),
                ('key', models.CharField(max_length=64, serialize=False, primary_key=True)),
                ('data', models.TextField(default='')),
                ('attr1', models.CharField(default=None, max_length=64, null=True, db_index=True, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Transport',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=128)),
                ('data_type', models.CharField(max_length=128)),
                ('data', models.TextField(default='')),
                ('comments', models.CharField(max_length=256)),
                ('priority', models.IntegerField(default=0, db_index=True)),
                ('nets_positive', models.BooleanField(default=False)),
            ],
            options={
                'ordering': ('name',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='UniqueId',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('owner', models.CharField(default='', max_length=128, db_index=True)),
                ('basename', models.CharField(max_length=32, db_index=True)),
                ('seq', models.BigIntegerField(db_index=True)),
                ('assigned', models.BooleanField(default=True, db_index=True)),
                ('stamp', models.IntegerField(default=0, db_index=True)),
            ],
            options={
                'ordering': ('-seq',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, db_index=True)),
                ('real_name', models.CharField(max_length=128)),
                ('comments', models.CharField(max_length=256)),
                ('state', models.CharField(max_length=1, db_index=True)),
                ('password', models.CharField(default='', max_length=128)),
                ('staff_member', models.BooleanField(default=False)),
                ('is_admin', models.BooleanField(default=False)),
                ('last_access', models.DateTimeField(default=datetime.datetime(1972, 7, 1, 0, 0))),
                ('parent', models.IntegerField(default=-1)),
                ('manager', models.ForeignKey(related_name='users', to='uds.Authenticator')),
            ],
            options={
                'ordering': ('name',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='UserPreference',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('module', models.CharField(max_length=32, db_index=True)),
                ('name', models.CharField(max_length=32, db_index=True)),
                ('value', models.CharField(max_length=128, db_index=True)),
                ('user', models.ForeignKey(related_name='preferences', to='uds.User')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='UserService',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('unique_id', models.CharField(default='', max_length=128, db_index=True)),
                ('friendly_name', models.CharField(default='', max_length=128)),
                ('state', models.CharField(default='P', max_length=1, db_index=True)),
                ('os_state', models.CharField(default='P', max_length=1)),
                ('state_date', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('creation_date', models.DateTimeField(db_index=True)),
                ('data', models.TextField(default='')),
                ('in_use', models.BooleanField(default=False)),
                ('in_use_date', models.DateTimeField(default=datetime.datetime(1972, 7, 1, 0, 0))),
                ('cache_level', models.PositiveSmallIntegerField(default=0, db_index=True)),
                ('src_hostname', models.CharField(default='', max_length=64)),
                ('src_ip', models.CharField(default='', max_length=15)),
                ('cluster_node', models.CharField(default=None, max_length=128, null=True, db_index=True, blank=True)),
                ('deployed_service', models.ForeignKey(related_name='userServices', to='uds.DeployedService')),
                ('publication', models.ForeignKey(related_name='userServices', blank=True, to='uds.DeployedServicePublication', null=True)),
                ('user', models.ForeignKey(related_name='userServices', default=None, blank=True, to='uds.User', null=True)),
            ],
            options={
                'ordering': ('creation_date',),
                'db_table': 'uds__user_service',
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='user',
            unique_together=set([('manager', 'name')]),
        ),
        migrations.AlterUniqueTogether(
            name='uniqueid',
            unique_together=set([('basename', 'seq')]),
        ),
        migrations.AlterUniqueTogether(
            name='service',
            unique_together=set([('provider', 'name')]),
        ),
        migrations.AddField(
            model_name='network',
            name='transports',
            field=models.ManyToManyField(related_name='networks', db_table='uds_net_trans', to='uds.Transport'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='group',
            name='users',
            field=models.ManyToManyField(related_name='groups', to='uds.User'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='group',
            unique_together=set([('manager', 'name')]),
        ),
        migrations.AddField(
            model_name='deployedservice',
            name='assignedGroups',
            field=models.ManyToManyField(related_name='deployedServices', db_table='uds__ds_grps', to='uds.Group'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='deployedservice',
            name='osmanager',
            field=models.ForeignKey(related_name='deployedServices', blank=True, to='uds.OSManager', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='deployedservice',
            name='service',
            field=models.ForeignKey(related_name='deployedServices', blank=True, to='uds.Service', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='deployedservice',
            name='transports',
            field=models.ManyToManyField(related_name='deployedServices', db_table='uds__ds_trans', to='uds.Transport'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='config',
            unique_together=set([('section', 'key')]),
        ),
    ]
