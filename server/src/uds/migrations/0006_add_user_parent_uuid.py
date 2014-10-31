# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def add_parent_uuids(apps, schema_editor):
    '''
    Adds uuids values to migrated models
    '''
    model = apps.get_model("uds", 'User')
    for m in model.objects.all():
        print m
        parent = int(m.parent)
        if parent != -1:
            try:
                parent = model.objects.get(pk=parent).uuid
            except Exception:
                parent = None
        else:
            parent = None
        m.parent = parent
        m.save()


def remove_parent_uuids(apps, schema_editor):
    '''
    Dummy function. uuid field will be dropped on reverse migration
    '''
    model = apps.get_model("uds", 'User')
    for m in model.objects.all():
        parent = m.parent
        if parent is not None and parent != '':
            try:
                parent = model.objects.get(uuid=parent).id
            except Exception:
                parent = -1
        else:
            parent = -1
        m.parent = parent
        m.save()


class Migration(migrations.Migration):

    dependencies = [
        ('uds', '0005_userservice_comms_url'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='parent',
            field=models.CharField(default=None, max_length=50, null=True),
            preserve_default=True,
        ),
        migrations.RunPython(
            add_parent_uuids,
            remove_parent_uuids
        ),

    ]
