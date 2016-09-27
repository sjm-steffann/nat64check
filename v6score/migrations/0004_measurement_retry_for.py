# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('v6score', '0003_auto_20160927_1653'),
    ]

    operations = [
        migrations.AddField(
            model_name='measurement',
            name='retry_for',
            field=models.ForeignKey(to='v6score.Measurement', blank=True, null=True),
        ),
    ]
