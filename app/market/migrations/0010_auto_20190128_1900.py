# Generated by Django 2.1.2 on 2019-01-28 19:00

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('eve_api', '0001_initial'),
        ('market', '0009_tradingroute_last_viewed'),
    ]

    operations = [
        migrations.AlterIndexTogether(
            name='markethistory',
            index_together={('region', 'date', 'object_type')},
        ),
    ]
