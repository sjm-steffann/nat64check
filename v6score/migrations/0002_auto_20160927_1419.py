# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('v6score', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='measurement',
            name='v6only_score',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='measurement',
            name='nat64_score',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.RunSQL([
            "UPDATE v6score_measurement SET v6only_score=NULL WHERE v6only_score=-1",
            "UPDATE v6score_measurement SET nat64_score=NULL WHERE nat64_score=-1",
        ], [
            "UPDATE v6score_measurement SET v6only_score=-1 WHERE v6only_score IS NULL",
            "UPDATE v6score_measurement SET nat64_score=-1 WHERE nat64_score IS NULL",
        ])
    ]
