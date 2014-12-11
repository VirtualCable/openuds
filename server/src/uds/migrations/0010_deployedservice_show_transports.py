# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('uds', '0009_TransportsToNewerModel'),
    ]

    operations = [
        migrations.AddField(
            model_name='deployedservice',
            name='show_transports',
            field=models.BooleanField(default=True),
            preserve_default=True,
        ),
    ]
