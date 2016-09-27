# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('v6score', '0002_auto_20160927_1419'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='website',
            options={'ordering': ('hostname',)},
        ),
        migrations.AddField(
            model_name='measurement',
            name='manual',
            field=models.BooleanField(default=False),
        ),
    ]
