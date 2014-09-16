# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('uds', '0003_add_uuids'),
    ]

    operations = [
        migrations.AlterField(
            model_name='authenticator',
            name='comments',
            field=models.CharField(max_length=256),
        ),
        migrations.AlterField(
            model_name='authenticator',
            name='name',
            field=models.CharField(max_length=128, db_index=True),
        ),
        migrations.AlterField(
            model_name='osmanager',
            name='name',
            field=models.CharField(max_length=128, db_index=True),
        ),
        migrations.AlterField(
            model_name='provider',
            name='name',
            field=models.CharField(max_length=128, db_index=True),
        ),
        migrations.AlterField(
            model_name='service',
            name='name',
            field=models.CharField(max_length=128, db_index=True),
        ),
        migrations.AlterField(
            model_name='transport',
            name='name',
            field=models.CharField(max_length=128, db_index=True),
        ),
    ]
