# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('uds', '0013_statsevents_fld4'),
    ]

    operations = [
        migrations.CreateModel(
            name='Permissions',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', models.CharField(default=None, max_length=50, unique=True, null=True)),
                ('created', models.DateTimeField(db_index=True)),
                ('ends', models.DateTimeField(default=None, null=True, db_index=True, blank=True)),
                ('object_type', models.SmallIntegerField(default=-1, db_index=True)),
                ('object_id', models.IntegerField(default=None, null=True, db_index=True, blank=True)),
                ('permission', models.SmallIntegerField(default=0, db_index=True)),
                ('group', models.ForeignKey(related_name='permissions', default=None, blank=True, to='uds.Group', null=True)),
                ('user', models.ForeignKey(related_name='permissions', default=None, blank=True, to='uds.User', null=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
    ]
