# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('uds', '0020_auto_20160216_0509'),
    ]

    operations = [
        migrations.CreateModel(
            name='CalendarAccess',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('allow', models.BooleanField(default=True)),
                ('priority', models.IntegerField(default=0, db_index=True)),
                ('calendar', models.ForeignKey(to='uds.Calendar')),
            ],
            options={
                'db_table': 'uds_cal_access',
            },
        ),
        migrations.CreateModel(
            name='CalendarAction',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('action', models.CharField(max_length=64)),
                ('params', models.CharField(max_length=1024)),
                ('calendar', models.ForeignKey(to='uds.Calendar')),
            ],
            options={
                'db_table': 'uds_cal_action',
            },
        ),
        migrations.AddField(
            model_name='deployedservice',
            name='fallbackAccessAllow',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='calendaraction',
            name='servicePool',
            field=models.ForeignKey(to='uds.DeployedService'),
        ),
        migrations.AddField(
            model_name='calendaraccess',
            name='servicePool',
            field=models.ForeignKey(to='uds.DeployedService'),
        ),
        migrations.AddField(
            model_name='deployedservice',
            name='accessCalendars',
            field=models.ManyToManyField(related_name='accessSP', through='uds.CalendarAccess', to='uds.Calendar'),
        ),
        migrations.AddField(
            model_name='deployedservice',
            name='actionsCalendars',
            field=models.ManyToManyField(related_name='actionsSP', through='uds.CalendarAction', to='uds.Calendar'),
        ),
    ]
