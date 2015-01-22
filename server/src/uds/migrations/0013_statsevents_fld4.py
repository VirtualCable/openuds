# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('uds', '0012_auto_20141221_1210'),
    ]

    operations = [
        migrations.AddField(
            model_name='statsevents',
            name='fld4',
            field=models.CharField(default='', max_length=128),
            preserve_default=True,
        ),
    ]
