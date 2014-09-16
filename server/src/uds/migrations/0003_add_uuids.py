# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from uds.core.util.model import generateUuid


def add_uuids(apps, schema_editor):
    '''
    Adds uuids values to migrated models
    '''
    for model in ('Authenticator', 'Group', 'Network', 'UserService',
                  'OSManager', 'Provider', 'Service', 'DeployedService',
                  'DeployedServicePublication', 'Transport', 'User'):
        Model = apps.get_model("uds", model)
        for m in Model.objects.all():
            m.uuid = generateUuid()
            m.save()


def remove_uuids(apps, schema_editor):
    '''
    Dummy function. uuid field will be dropped on reverse migration
    '''
    pass


class Migration(migrations.Migration):
    '''
    Implements the migrations needed to add uuid to manageable objects
    '''
    dependencies = [
        ('uds', '0002_auto_20140908_1344'),
    ]

    operations = [
        migrations.AddField(
            model_name='userservice',
            name='uuid',
            field=models.CharField(default=None, max_length=50, unique=True, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='authenticator',
            name='uuid',
            field=models.CharField(default=None, max_length=50, unique=True, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='group',
            name='uuid',
            field=models.CharField(default=None, max_length=50, unique=True, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='network',
            name='uuid',
            field=models.CharField(default=None, max_length=50, unique=True, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='osmanager',
            name='uuid',
            field=models.CharField(default=None, max_length=50, unique=True, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='provider',
            name='uuid',
            field=models.CharField(default=None, max_length=50, unique=True, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='service',
            name='uuid',
            field=models.CharField(default=None, max_length=50, unique=True, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='deployedservice',
            name='uuid',
            field=models.CharField(default=None, max_length=50, unique=True, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='deployedservicepublication',
            name='uuid',
            field=models.CharField(default=None, max_length=50, unique=True, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='transport',
            name='uuid',
            field=models.CharField(default=None, max_length=50, unique=True, null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='user',
            name='uuid',
            field=models.CharField(default=None, max_length=50, unique=True, null=True),
            preserve_default=True,
        ),
        migrations.RunPython(
            add_uuids,
            remove_uuids
        ),
    ]
