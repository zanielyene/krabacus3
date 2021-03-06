# Generated by Django 2.1.2 on 2019-01-03 18:37

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('eve_api', '0001_initial'),
        ('market', '0002_auto_20181214_1939'),
    ]

    operations = [
        migrations.CreateModel(
            name='MarketHistoryScanLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('scan_start', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('scan_complete', models.DateTimeField(db_index=True, default=None, null=True)),
                ('region', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='eve_api.Region')),
            ],
        ),
        migrations.CreateModel(
            name='StructureMarketScanLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('scan_start', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('scan_complete', models.DateTimeField(db_index=True, default=None, null=True)),
                ('structure', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='eve_api.Structure')),
            ],
        ),
        migrations.AlterIndexTogether(
            name='structuremarketscanlog',
            index_together={('structure', 'scan_start'), ('structure', 'scan_complete')},
        ),
        migrations.AlterIndexTogether(
            name='markethistoryscanlog',
            index_together={('region', 'scan_complete'), ('region', 'scan_start')},
        ),
    ]
