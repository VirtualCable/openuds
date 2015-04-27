# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
import uds.models.Util


class Migration(migrations.Migration):

    dependencies = [
        ('uds', '0015_ticketstore'),
    ]

    operations = [
        migrations.AlterField(
            model_name='deployedservice',
            name='image',
            field=models.ForeignKey(related_name='deployedServices', on_delete=django.db.models.deletion.SET_NULL, blank=True, to='uds.Image', null=True),
        ),
        migrations.AlterField(
            model_name='group',
            name='manager',
            field=uds.models.Util.UnsavedForeignKey(related_name='groups', to='uds.Authenticator'),
        ),
        migrations.AlterField(
            model_name='user',
            name='manager',
            field=uds.models.Util.UnsavedForeignKey(related_name='users', to='uds.Authenticator'),
        ),
    ]
