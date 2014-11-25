# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('uds', '0007_image'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserServiceProperty',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, db_index=True)),
                ('value', models.TextField(default='')),
                ('user_service', models.ForeignKey(related_name='properties', to='uds.UserService')),
            ],
            options={
                'db_table': 'uds__user_service_property',
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='userserviceproperty',
            unique_together=set([('name', 'user_service')]),
        ),
    ]
