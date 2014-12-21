# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('uds', '0010_deployedservice_show_transports'),
    ]

    operations = [
        migrations.AddField(
            model_name='deployedservice',
            name='meta_pools',
            field=models.ManyToManyField(to='uds.DeployedService'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='provider',
            name='maintenance_mode',
            field=models.BooleanField(default=False, db_index=True),
            preserve_default=True,
        ),
    ]
