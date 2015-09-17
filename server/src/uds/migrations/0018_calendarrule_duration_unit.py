# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('uds', '0017_calendar_calendarrule'),
    ]

    operations = [
        migrations.AddField(
            model_name='calendarrule',
            name='duration_unit',
            field=models.CharField(default='MINUTES', max_length=32, choices=[('MINUTES', 'Minutes'), ('HOURS', 'Hours'), ('DAYS', 'Days'), ('WEEKS', 'Weeks')]),
        ),
    ]
