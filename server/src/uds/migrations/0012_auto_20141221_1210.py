# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('uds', '0011_auto_20141220_1203'),
    ]

    operations = [
        migrations.AddField(
            model_name='statsevents',
            name='fld1',
            field=models.CharField(default='', max_length=128),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='statsevents',
            name='fld2',
            field=models.CharField(default='', max_length=128),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='statsevents',
            name='fld3',
            field=models.CharField(default='', max_length=128),
            preserve_default=True,
        ),
    ]
