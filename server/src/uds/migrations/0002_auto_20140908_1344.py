# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('uds', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='network',
            options={'ordering': ('name',)},
        ),
        migrations.AddField(
            model_name='config',
            name='field_type',
            field=models.IntegerField(default=-1),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='group',
            name='meta_if_any',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
