# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('uds', '0014_permissions'),
    ]

    operations = [
        migrations.CreateModel(
            name='TicketStore',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', models.CharField(default=None, max_length=50, unique=True, null=True)),
                ('stamp', models.DateTimeField()),
                ('validity', models.IntegerField(default=60)),
                ('data', models.BinaryField()),
                ('validator', models.BinaryField(default=None, null=True, blank=True)),
            ],
            options={
                'db_table': 'uds_tickets',
            },
            bases=(models.Model,),
        ),
    ]
