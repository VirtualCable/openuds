# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('uds', '0018_auto_20151005_1305'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', models.CharField(default=None, max_length=50, unique=True, null=True)),
                ('tag', models.CharField(unique=True, max_length=32, db_index=True)),
            ],
            options={
                'db_table': 'uds_tag',
            },
        ),
        migrations.AddField(
            model_name='authenticator',
            name='tags',
            field=models.ManyToManyField(to='uds.Tag'),
        ),
        migrations.AddField(
            model_name='calendar',
            name='tags',
            field=models.ManyToManyField(to='uds.Tag'),
        ),
        migrations.AddField(
            model_name='deployedservice',
            name='tags',
            field=models.ManyToManyField(to='uds.Tag'),
        ),
        migrations.AddField(
            model_name='network',
            name='tags',
            field=models.ManyToManyField(to='uds.Tag'),
        ),
        migrations.AddField(
            model_name='osmanager',
            name='tags',
            field=models.ManyToManyField(to='uds.Tag'),
        ),
        migrations.AddField(
            model_name='provider',
            name='tags',
            field=models.ManyToManyField(to='uds.Tag'),
        ),
        migrations.AddField(
            model_name='service',
            name='tags',
            field=models.ManyToManyField(to='uds.Tag'),
        ),
        migrations.AddField(
            model_name='transport',
            name='tags',
            field=models.ManyToManyField(to='uds.Tag'),
        ),
    ]
