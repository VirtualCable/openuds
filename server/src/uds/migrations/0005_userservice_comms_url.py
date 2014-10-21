# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('uds', '0004_auto_20140916_1217'),
    ]

    operations = [
        migrations.AddField(
            model_name='userservice',
            name='comms_url',
            field=models.CharField(default=None, max_length=256, null=True, blank=True),
            preserve_default=True,
        ),
    ]
