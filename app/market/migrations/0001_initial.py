# Generated by Django 2.1.2 on 2018-11-21 21:08

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('eve_api', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ItemGroup',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=190)),
                ('creator', models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('items', models.ManyToManyField(to='eve_api.ObjectType')),
            ],
        ),
        migrations.CreateModel(
            name='MarketHistory',
            fields=[
                ('id', models.BigAutoField(editable=False, primary_key=True, serialize=False)),
                ('date', models.DateField()),
                ('average', models.FloatField()),
                ('highest', models.FloatField()),
                ('lowest', models.FloatField()),
                ('order_count', models.BigIntegerField()),
                ('volume', models.BigIntegerField()),
                ('object_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='eve_api.ObjectType')),
                ('region', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='eve_api.Region')),
            ],
        ),
        migrations.CreateModel(
            name='MarketOrder',
            fields=[
                ('ccp_id', models.BigIntegerField(editable=False, primary_key=True, serialize=False)),
                ('order_active', models.BooleanField(default=True)),
                ('duration', models.IntegerField()),
                ('is_buy_order', models.BooleanField()),
                ('issued', models.DateTimeField()),
                ('min_volume', models.BigIntegerField()),
                ('price', models.FloatField()),
                ('range', models.CharField(max_length=20)),
                ('volume_remain', models.BigIntegerField()),
                ('volume_total', models.BigIntegerField()),
                ('character', models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to='eve_api.EVEPlayerCharacter')),
                ('location', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='eve_api.Structure')),
                ('object_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='eve_api.ObjectType')),
            ],
        ),
        migrations.CreateModel(
            name='PlayerTransaction',
            fields=[
                ('ccp_id', models.BigIntegerField(primary_key=True, serialize=False)),
                ('client_id', models.BigIntegerField()),
                ('timestamp', models.DateTimeField()),
                ('is_buy', models.BooleanField()),
                ('is_personal', models.BooleanField()),
                ('journal_ref_id', models.BigIntegerField()),
                ('quantity', models.BigIntegerField()),
                ('unit_price', models.FloatField()),
                ('quantity_without_known_source', models.BigIntegerField()),
                ('quantity_without_known_destination', models.BigIntegerField()),
                ('character', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='eve_api.EVEPlayerCharacter')),
                ('location', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='eve_api.Structure')),
                ('object_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='eve_api.ObjectType')),
            ],
        ),
        migrations.CreateModel(
            name='TradingRoute',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('source_character_has_access', models.BooleanField(default=True)),
                ('destination_character_has_access', models.BooleanField(default=True)),
                ('cost_per_m3', models.IntegerField()),
                ('pct_collateral', models.FloatField()),
                ('sales_tax', models.FloatField()),
                ('broker_fee', models.FloatField(default=None, null=True)),
                ('creator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('destination_character', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='destination_character', to='eve_api.EVEPlayerCharacter')),
                ('destination_structure', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='destination_structure', to='eve_api.Structure')),
                ('item_groups', models.ManyToManyField(to='market.ItemGroup')),
                ('source_character', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='source_character', to='eve_api.EVEPlayerCharacter')),
                ('source_structure', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='source_structure', to='eve_api.Structure')),
            ],
        ),
        migrations.CreateModel(
            name='TransactionLinkage',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('quantity_linked', models.BigIntegerField()),
                ('date_linked', models.DateTimeField(default=django.utils.timezone.now)),
                ('destination_transaction', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='destination_transaction', to='market.PlayerTransaction')),
                ('route', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='market.TradingRoute')),
                ('source_transaction', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='source_transaction', to='market.PlayerTransaction')),
            ],
        ),
        migrations.AlterIndexTogether(
            name='transactionlinkage',
            index_together={('route', 'date_linked')},
        ),
        migrations.AlterIndexTogether(
            name='playertransaction',
            index_together={('location', 'object_type', 'character', 'timestamp', 'is_buy')},
        ),
        migrations.AlterIndexTogether(
            name='marketorder',
            index_together={('location', 'object_type', 'order_active', 'is_buy_order')},
        ),
        migrations.AlterIndexTogether(
            name='markethistory',
            index_together={('object_type', 'region', 'date')},
        ),
    ]
