# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2016-11-20 16:34
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('v6score', '0014_auto_20161120_1523'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='measurement',
            name='website',
        ),
        migrations.DeleteModel(
            name='Website',
        ),
    ]