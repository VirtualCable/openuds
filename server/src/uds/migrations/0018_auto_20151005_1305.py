# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('uds', '0017_calendar_calendarrule'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scheduler',
            name='last_execution',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AlterIndexTogether(
            name='userservice',
            index_together=set([('deployed_service', 'cache_level', 'state')]),
        ),
    ]
