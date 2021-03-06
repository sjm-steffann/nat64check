# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2016-09-29 15:31
from __future__ import unicode_literals

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('v6score', '0005_auto_20160927_2005'),
    ]

    operations = [
        migrations.AddField(
            model_name='measurement',
            name='nat64_data',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='measurement',
            name='nat64_debug',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='measurement',
            name='v4only_data',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='measurement',
            name='v4only_debug',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='measurement',
            name='v6only_data',
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='measurement',
            name='v6only_debug',
            field=models.TextField(blank=True),
        ),
    ]
