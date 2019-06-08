import logging
from django.contrib.auth.models import User
import asyncio

from django.db import models
from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

from eve_api.models import Structure, EVEPlayerCharacter, ObjectType
from .player_transaction import PlayerTransaction
from market.utils import get_cached_column, obj_exists_cached
from conf.huey_queues import general_queue
logger=logging.getLogger(__name__)


class MarketOrder(models.Model):
    ccp_id = models.BigIntegerField(primary_key=True, editable=False)

    character = models.ForeignKey(EVEPlayerCharacter, default=None, null=True, on_delete=models.CASCADE)

    order_active = models.BooleanField(default=True)
    duration = models.IntegerField()
    is_buy_order = models.BooleanField()
    issued = models.DateTimeField()
    location = models.ForeignKey(Structure, on_delete=models.CASCADE)
    min_volume = models.BigIntegerField()
    price = models.FloatField()
    range = models.CharField(max_length = 20)
    object_type = models.ForeignKey(ObjectType, on_delete=models.CASCADE)
    volume_remain = models.BigIntegerField()
    volume_total = models.BigIntegerField()

    def __str__(self):
        return "Order #{}".format(self.ccp_id)

    @staticmethod
    def get_market_order_cache_timeout():
        # 30 days is a good half-life for orders i think
        return 30 * 86400


    @staticmethod
    def exists(ccp_id):
        return obj_exists_cached(
            "market_order_exists_{}",
            ccp_id,
            MarketOrder
        )

    @staticmethod
    def get_price(ccp_id):
        return get_cached_column(
            cache_key = "market_order_price_{}",
            primary_key = ccp_id,
            model = MarketOrder,
            col_name = 'price'
        )

    @staticmethod
    def get_volume_remain(ccp_id):
        return get_cached_column(
            cache_key = "market_order_vol_remain_{}",
            primary_key = ccp_id,
            model = MarketOrder,
            col_name = 'volume_remain'
        )

    @staticmethod
    def set_order_owner(character, order_ids):
        """
        Attempt to attribute the given order_ids to the given character.
        Returns a list of orders that we do NOT have on record, and thus need to be initialized.
        :param character:
        :param orders:
        :return:
        """
        orders = MarketOrder.objects.filter(ccp_id__in=order_ids)

        orders_we_have = orders.values_list('ccp_id', flat=True)
        orders_we_dont_have = set(order_ids) - set(orders_we_have)

        # now update orders
        orders.update(character=character)

        return orders_we_dont_have


    @staticmethod
    def get_order_prices_and_volume(orders):
        keys = []
        for order in orders:
            keys.append("market_order_price_{}".format(order["order_id"]))
            keys.append("market_order_vol_remain_{}".format(order["order_id"]))

        cache_res = cache.get_many(keys)

        # todo: remove this async trash
        async def load_values(order):
            price_key = "market_order_price_{}".format(order["order_id"])
            if price_key not in cache_res:
                price = MarketOrder.get_price(order["order_id"])
            else:
                price = cache_res[price_key]

            volume_key = "market_order_vol_remain_{}".format(order["order_id"])
            if volume_key not in cache_res:
                volume = MarketOrder.get_volume_remain(order["order_id"])
            else:
                volume = cache_res[volume_key]

            return order["order_id"], price, volume

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        f =  asyncio.gather(*[load_values(order) for order in orders])
        results = loop.run_until_complete(f)
        loop.close()

        prices = {}
        volumes = {}

        for order_id, price, volume in results:
            prices[order_id] = price
            volumes[order_id] = volume

        return prices, volumes


    @staticmethod
    def get_minimum_sell_price(object_type, structure):
        orders = MarketOrder.objects.filter(
            object_type=object_type,
            location=structure,
            order_active=True,
            is_buy_order=False
        ).order_by('price')

        best_order = orders.first()
        return best_order.price if best_order else None

    @staticmethod
    def populate_cache_for_new_objects(objects):
        keys = {}
        for o in objects:
            keys["market_order_exists_{}".format(o.ccp_id)] = True
            keys["market_order_price_{}".format(o.ccp_id)] = o.price
            keys["market_order_vol_remain_{}".format(o.ccp_id)] = o.volume_remain

        cache.set_many(keys, timeout=MarketOrder.get_market_order_cache_timeout())

    def calculate_current_breakeven(self, route):
        # we have two ways to calculate how much the item costs at the hub
        # 1. the good way: locate a source transaction that accounts for all the volume of this order, and use the price
        #    that transaction occurred at
        # 2. the bad way: use whatever the lowest sell price is in the source market hub.

        import_cost = route.calculate_import_cost(self.object_type)

        unaccounted, txns = PlayerTransaction.search_for_source_transactions(route, self.object_type, 1)
        if unaccounted:
            # we have to use the source hub's sell price, sucks to suck
            item_price = MarketOrder.get_minimum_sell_price(self.object_type, route.source_character)
            if item_price is None:
                raise Exception("no source data")
        else:
            item_price = txns[0]["transaction"].unit_price

        return import_cost + item_price


    class Meta:
        index_together = [
            ["location", "object_type","order_active","is_buy_order"]
        ]


    @staticmethod
    def heat_cache():
        keys = {}
        logger.info("Heating market order cache (order_exists, order_price, order_vol_remain)")
        orders = MarketOrder.objects.filter(order_active=True).values('ccp_id', 'price', 'volume_remain')
        for order in orders:
            keys["market_order_exists_{}".format(order["ccp_id"])] = True
            keys["market_order_price_{}".format(order["ccp_id"])] = order["price"]
            keys["market_order_vol_remain_{}".format(order["ccp_id"])] = order["volume_remain"]

        cache.set_many(keys, timeout=MarketOrder.get_market_order_cache_timeout())
        logger.info("Market order cache hot with {} kv's".format(len(keys)))

@receiver(post_save, sender=MarketOrder)
def market_order_invalidator(sender, instance, **kwargs):
    d = {
        'market_order_price_{}'.format(instance.pk): instance.price,
        "market_order_vol_remain_{}".format(instance.pk): instance.volume_remain
    }
    cache.set_many(d, timeout=MarketOrder.get_market_order_cache_timeout())




# debatable
#class MarketOrderDelta(models.Model):
#    order = models.ForeignKey(MarketOrder, on_delete=models.CASCADE)
#    delta_amount = models.BigIntegerField()
#    delta_recorded = models.DateTimeField()


