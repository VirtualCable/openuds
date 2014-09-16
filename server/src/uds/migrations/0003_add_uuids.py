# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations

from uds.core.util.model import generateUuid


def add_uuids(apps, schema_editor):
    # We can't import the Person model directly as it may be a newer
    # version than this migration expects. We use the historical version.
    for model in ('Authenticator', 'Group', 'Network', 'UserService', 'OSManager', 'Provider'):
        Model = apps.get_model("uds", model)
        for m in Model.objects.all():
            m.uuid = generateUuid()
            m.save()


def remove_uuids(apps, schema_editor):
    pass


class Migration(migrations.Migration):

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
        migrations.RunPython(
            add_uuids,
            remove_uuids
        ),
    ]
