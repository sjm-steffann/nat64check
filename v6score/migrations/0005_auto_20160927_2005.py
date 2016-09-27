# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('v6score', '0004_measurement_retry_for'),
    ]

    operations = [
        migrations.AlterField(
            model_name='measurement',
            name='requested',
            field=models.DateTimeField(),
        ),
    ]
