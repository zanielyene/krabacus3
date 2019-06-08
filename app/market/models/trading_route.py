import logging
import uuid
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from eve_api.models import Structure, EVEPlayerCharacter, ObjectType
from .market_order import MarketOrder
from .item_group import ItemGroup
from .player_transaction import PlayerTransaction

logger=logging.getLogger(__name__)


class TradingRoute(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(User, on_delete=models.CASCADE)
    date_created = models.DateTimeField(default=timezone.now)
    colorblind = models.BooleanField(default=False)

    source_structure = models.ForeignKey(Structure, related_name="source_structure", on_delete=models.CASCADE)
    source_character = models.ForeignKey(EVEPlayerCharacter, related_name="source_character", on_delete=models.CASCADE)
    source_character_has_access = models.BooleanField(default=True)

    destination_structure = models.ForeignKey(Structure, related_name="destination_structure", on_delete=models.CASCADE)
    destination_character = models.ForeignKey(EVEPlayerCharacter, related_name="destination_character", on_delete=models.CASCADE)
    destination_character_has_access = models.BooleanField(default=True)

    cost_per_m3 = models.IntegerField()
    pct_collateral = models.FloatField()

    sales_tax = models.FloatField()
    broker_fee = models.FloatField(default=None,null=True)

    last_viewed = models.DateTimeField(default=None, null=True)

    item_groups = models.ManyToManyField(ItemGroup)

    @property
    def items(self):
        # todo: cache?
        return list(set(ObjectType.objects.filter(itemgroup__tradingroute=self)))

    @property
    def item_ids(self):
        # todo: cache?
        return list(set(ObjectType.objects.filter(itemgroup__tradingroute=self).values_list('ccp_id',flat=True)))

    def calculate_import_cost(self, object_type, quantity=1):
        # todo: remove?
        price = MarketOrder.get_minimum_sell_price(object_type, self.source_structure)
        if price is None:
            return None

        total_cost = price * float(quantity)
        collateral_cost = total_cost * self.pct_collateral

        volume_cost = self.calculate_freight(object_type, quantity)

        return collateral_cost + volume_cost

    def calculate_freight_m3(self, object_type, quantity=1):
        return object_type.packaged_volume * float(quantity) * float(self.cost_per_m3)

    def calculate_cogs_from_linkage(self, linkage):
        obj_type = linkage.source_transaction.object_type
        item_cost = linkage.source_transaction.unit_price * linkage.quantity_linked
        freight_cost_m3 = self.calculate_freight_m3(obj_type, linkage.quantity_linked)
        freight_cost_collat = item_cost * self.pct_collateral / 100
        fees = (self.broker_fee + self.sales_tax) / 100.0 * linkage.quantity_linked * linkage.destination_transaction.unit_price
        #print("tot cost: {}  freight m3 cost: {}  freight collat: {} fees: {}  units: {}".format(item_cost, freight_cost_m3, freight_cost_collat, fees, linkage.quantity_linked))
        return item_cost + freight_cost_collat + freight_cost_m3 + fees

    def estimate_cogs(self, object_type, quantity, unit_sell_price):
        possible_transactions = PlayerTransaction.objects.filter(
            character = self.source_character,
            location = self.source_structure,
            object_type = object_type,
            quantity_without_known_destination__gt=0
        ).order_by('unit_price')
        quantity_attributed = 0
        quantity_remaining = quantity
        value = 0.0
        for transaction in possible_transactions:
            if transaction.quantity_without_known_destination == quantity_remaining:
                q_attribed = quantity_remaining
            elif transaction.quantity_without_known_destination > quantity_remaining:
                q_attribed = quantity_remaining
            else:
                q_attribed = transaction.quantity_without_known_destination

            quantity_attributed += q_attribed
            quantity_remaining -= q_attribed
            value += q_attribed * transaction.unit_price
            if not quantity_remaining:
                break

        if quantity_remaining:
            # extrapolate for the rest
            if quantity_attributed:
                value = value * (quantity_attributed + quantity_remaining) / quantity_attributed
            else:
                # we have 0 quantity attributed.
                return None


        freight_cost_m3 = self.calculate_freight_m3(object_type, quantity)
        freight_cost_collat = value * self.pct_collateral / 100
        fees = (self.broker_fee + self.sales_tax) / 100.0 * quantity * unit_sell_price
        return value + freight_cost_collat + freight_cost_m3 + fees


    def __str__(self):
        return self.source_structure.location.system.name + " -> " + self.destination_structure.location.system.name
