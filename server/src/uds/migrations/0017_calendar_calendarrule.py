# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('uds', '0016_auto_20150617_0741'),
    ]

    operations = [
        migrations.CreateModel(
            name='Calendar',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', models.CharField(default=None, max_length=50, unique=True, null=True)),
                ('name', models.CharField(default='', max_length=128)),
                ('comments', models.CharField(default='', max_length=256)),
                ('modified', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'uds_calendar',
            },
        ),
        migrations.CreateModel(
            name='CalendarRule',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', models.CharField(default=None, max_length=50, unique=True, null=True)),
                ('name', models.CharField(max_length=128)),
                ('comments', models.CharField(max_length=256)),
                ('start', models.DateTimeField()),
                ('end', models.DateField(null=True, blank=True)),
                ('frequency', models.CharField(max_length=32, choices=[('YEARLY', 'Yearly'), ('MONTHLY', 'Monthly'), ('WEEKLY', 'Weekly'), ('DAILY', 'Daily'), ('WEEKDAYS', 'Weekdays')])),
                ('interval', models.IntegerField(default=1)),
                ('duration', models.IntegerField(default=0)),
                ('duration_unit', models.CharField(default='MINUTES', max_length=32, choices=[('MINUTES', 'Minutes'), ('HOURS', 'Hours'), ('DAYS', 'Days'), ('WEEKS', 'Weeks')])),
                ('calendar', models.ForeignKey(related_name='rules', to='uds.Calendar')),
            ],
            options={
                'db_table': 'uds_calendar_rules',
            },
        ),
    ]
