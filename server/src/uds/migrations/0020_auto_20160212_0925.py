# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('uds', '0019_auto_20160210_0144'),
    ]

    operations = [
        migrations.CreateModel(
            name='ServicesPoolGroup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', models.CharField(default=None, max_length=50, unique=True, null=True)),
                ('name', models.CharField(default='', max_length=128)),
                ('comments', models.CharField(default='', max_length=256)),
                ('priority', models.IntegerField(default=0, db_index=True)),
                ('image', models.ForeignKey(related_name='servicesPoolsGrou', on_delete=django.db.models.deletion.SET_NULL, blank=True, to='uds.Image', null=True)),
            ],
            options={
                'abstract': False,
                'db_table': 'uds__pools_groups',
            },
        ),
        migrations.AddField(
            model_name='deployedservice',
            name='servicesPoolGroup',
            field=models.ForeignKey(related_name='servicesPools', on_delete=django.db.models.deletion.SET_NULL, blank=True, to='uds.ServicesPoolGroup', null=True),
        ),
    ]
