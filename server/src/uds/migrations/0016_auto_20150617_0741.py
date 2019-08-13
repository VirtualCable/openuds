# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
import uds.models.util


class Migration(migrations.Migration):

    dependencies = [
        ('uds', '0015_ticketstore'),
    ]

    operations = [
        migrations.CreateModel(
            name='DeployedServicePublicationChangelog',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('stamp', models.DateTimeField()),
                ('revision', models.PositiveIntegerField(default=1)),
                ('log', models.TextField(default='')),
            ],
            options={
                'abstract': False,
                'db_table': 'uds__deployed_service_pub_cl',
            },
        ),
        migrations.AddField(
            model_name='group',
            name='created',
            field=models.DateTimeField(default=uds.models.util.getSqlDatetime, blank=True),
        ),
        migrations.AddField(
            model_name='user',
            name='created',
            field=models.DateTimeField(default=uds.models.util.getSqlDatetime, blank=True),
        ),
        migrations.AlterField(
            model_name='deployedservice',
            name='image',
            field=models.ForeignKey(related_name='deployedServices', on_delete=django.db.models.deletion.SET_NULL, blank=True, to='uds.Image', null=True),
        ),
        migrations.AlterField(
            model_name='group',
            name='manager',
            field=uds.models.util.UnsavedForeignKey(related_name='groups', to='uds.Authenticator', on_delete=models.CASCADE),
        ),
        migrations.AlterField(
            model_name='user',
            name='manager',
            field=uds.models.util.UnsavedForeignKey(related_name='users', to='uds.Authenticator', on_delete=models.CASCADE),
        ),
        migrations.AddField(
            model_name='deployedservicepublicationchangelog',
            name='publication',
            field=models.ForeignKey(related_name='changelog', to='uds.DeployedService', on_delete=models.CASCADE),
        ),
    ]
