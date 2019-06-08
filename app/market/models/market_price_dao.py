import logging
from django.contrib.auth.models import User
import asyncio

from django.db import models
from django.core.cache import cache
from django.db.models.signals import post_save
from django.db.models import Sum, Avg, Max
from django.dispatch import receiver

from eve_api.models import Structure, EVEPlayerCharacter, ObjectType, Region
from django.utils import timezone
from datetime import timedelta
from enum import Enum
from market.models import MarketHistory
from market.models import MarketOrder
from .shopping_list import ShoppingListItem

import gevent
from gevent.pool import Pool


from market.models.util import get_structures_we_have_keys_for

logger=logging.getLogger(__name__)


class MarketDataType(Enum):
    item_id = 0
    item_name = 1
    shopping_list_id = 2
    shopping_list_qty = 3

    dest_volume_posted = 10
    dest_velocity = 11
    dest_depletion_estimate = 12
    dest_lowest_sell = 13
    dest_hanger_quantity = 14
    dest_max_sell_past_30 = 15

    src_volume_posted = 20
    src_velocity = 21 # n/i
    src_depletion_estimate = 22 # n/i
    src_lowest_sell = 23
    src_hanger_quantity = 24

    freight_cost_m3 = 30
    freight_cost_collat = 31
    freight_cost_total = 32
    broker_fee = 33
    sales_tax = 34
    listing_cost = 35

    cogs = 40
    unit_profit = 41
    projected_daily_profit = 42
    capital_efficiency = 43


class MarketPriceDAO:

    @staticmethod
    def get_market_dao_cache_timeout():
        # 31 days
        return 31 * 86400

    @staticmethod
    def purge_structure_price_cache(structure_id, object_ids):
        patterns = [
            "dao_lowest_sell_price_{}_{}",
            "dao_posted_order_volume_{}_{}",
            "dao_lowest_sell_order_{}_{}"
        ]

        patterns_to_delete = []
        for i in object_ids:
            patterns_to_delete.extend(
                [pattern.format(structure_id, i) for pattern in patterns]
            )

        cache.delete_many(patterns_to_delete)
        logger.info("Reheating DAO Price cache for {} object_types after partial purge".format(len(object_ids)))
        MarketPriceDAO.heat_price_cache(structure_id, object_ids)
        logger.info("DAO Price Cache hot")

    @staticmethod
    def purge_region_dao_cache(region_id, object_ids):
        # purge DAO velocity cache
        velocity_key = "dao_velocity_" + str(region_id) + "_30_{}"
        patterns_to_delete = [velocity_key.format(i) for i in object_ids]
        cache.delete_many(patterns_to_delete)
        logger.info("Reheating DAO velocity cache for {} object_types after partial purge".format(len(object_ids)))
        MarketPriceDAO.heat_velocity_cache(region_id, object_ids)
        logger.info("DAO velocity cache hot")

        # purge max price cache
        max_price_key = "dao_max_sell_" + str(region_id) + "_30_{}"
        patterns_to_delete = [max_price_key.format(i) for i in object_ids]
        cache.delete_many(patterns_to_delete)
        logger.info("Reheating DAO max price cache for {} object_types after partial purge".format(len(object_ids)))
        MarketPriceDAO.heat_max_price_cache(region_id, object_ids)
        logger.info("DAO max price cache hot")

    @staticmethod
    def heat_price_cache(structure_id=None, object_ids=None):
        if structure_id:
            structures = [Structure.get_object(structure_id, None)]
        else:
            structures = get_structures_we_have_keys_for()
            structures = [Structure.get_object(s, None) for s in structures]

        if not object_ids:
            object_ids = ObjectType.get_all_tradeable_items()

        logger.info("Heating object_id lowest sell price")
        for s in structures:
            MarketPriceDAO.get_lowest_sell_price_multi(object_ids, s)

        logger.info("Heating object_id volume posted")
        for s in structures:
            MarketPriceDAO.get_sell_volume_posted_multi(object_ids, s)

        logger.info("Heating object_id lowest order")
        for s in structures:
            MarketPriceDAO.get_lowest_sell_order_multi(object_ids, s)

    @staticmethod
    def heat_velocity_cache(region_id=None, object_ids=None):
        if region_id:
            distinct_regions = [region_id]
        else:
            distinct_regions = MarketHistory.objects.all().values_list('region_id', flat=True).distinct()

        for region_id in distinct_regions:
            region = Region.get_object(region_id)
            logger.info("Heating velocity cache for region {}".format(region.pk))
            oldest_order = timezone.now() - timedelta(days=30)
            if not object_ids:
                object_ids = MarketHistory.objects.filter(region=region, date__gte=oldest_order).values_list('object_type_id', flat=True).distinct()
            MarketPriceDAO.get_avg_velocity30_multi(object_ids, region)

    @staticmethod
    def heat_max_price_cache(region_id=None, object_ids=None):
        if region_id:
            distinct_regions = [region_id]
        else:
            distinct_regions = MarketHistory.objects.all().values_list('region_id', flat=True).distinct()

        for region_id in distinct_regions:
            region = Region.get_object(region_id)
            logger.info("Heating max sell price 30day for region {}".format(region.pk))
            oldest_order = timezone.now() - timedelta(days=30)
            if not object_ids:
                object_ids = MarketHistory.objects.filter(region=region, date__gte=oldest_order).values_list('object_type_id', flat=True).distinct()
            MarketPriceDAO.get_max_sell30_multi(object_ids, region)

    @staticmethod
    def heat_cache():
        logger.info("Heating price cache")
        MarketPriceDAO.heat_price_cache()
        logger.info("Market price cache hot")
        logger.info("Heating velocity cache")
        MarketPriceDAO.heat_velocity_cache()
        logger.info("Velocity cache hot")
        logger.info("Heating max price cache")
        MarketPriceDAO.heat_max_price_cache()
        logger.info("Max price cache hot")

    @staticmethod
    def _load_cached_range(
            object_type_ids,
            key_gen_func,
            calc_func,
    ):
        keys = [key_gen_func(i) for i in object_type_ids]

        res = cache.get_many(keys)
        ret = []
        keys_to_set = {}

        for obj_id, obj_key in zip(object_type_ids, keys):
            if obj_key in res:
                v = res[obj_key]
                if v == -1:
                    ret.append(None)
                else:
                    ret.append(v)
            else:
                v = calc_func(obj_id)
                ret.append(v)
                keys_to_set[obj_key] = -1 if v is None else v

        if keys_to_set:
            cache.set_many(keys_to_set, timeout=MarketPriceDAO.get_market_dao_cache_timeout())
        return ret

    @staticmethod
    def calculate_lowest_sell_price(object_type_id, structure):
        best_order = MarketOrder.objects.filter(
            location_id = structure.pk,
            object_type_id = object_type_id,
            is_buy_order = False,
            order_active = True
        ).order_by('price').first()

        # get all orders at this price

        if best_order is None:
            return None
        else:
            return best_order.price

    @staticmethod
    def calculate_lowest_sell_order(object_type_id, structure):
        best_order = MarketOrder.objects.filter(
            location_id = structure.pk,
            object_type_id = object_type_id,
            is_buy_order = False,
            order_active = True
        ).order_by('price').first()

        if best_order is None:
            return None
        else:
            orders_at_price = MarketOrder.objects.filter(
                location_id=structure.pk,
                object_type_id=object_type_id,
                is_buy_order=False,
                order_active=True,
                price=best_order.price
            ).values_list('ccp_id', flat=True)
            return list(orders_at_price)

    @staticmethod
    def calculate_posted_volume(object_type_id, is_buy_order, structure):
        s = MarketOrder.objects.filter(
            location_id = structure.pk,
            object_type_id = object_type_id,
            is_buy_order = is_buy_order,
            order_active = True
        ).aggregate(Sum('volume_remain'))
        return s["volume_remain__sum"]

    @staticmethod
    def calculate_avg_velocity_30day(object_type_id, region_id):
        thiry_ago = (timezone.now() - timedelta(days=30)).date()
        moved = MarketHistory.objects.filter(
            region_id = region_id,
            date__gte=thiry_ago,
            object_type_id=object_type_id
        ).aggregate(Sum('volume'))["volume__sum"]
        moved = 0 if moved is None else moved
        return float(moved) / 30.0

    @staticmethod
    def calculate_max_sell_30day(object_type_id, region_id):
        thiry_ago = (timezone.now() - timedelta(days=30)).date()
        max = MarketHistory.objects.filter(
            region_id = region_id,
            date__gte=thiry_ago,
            object_type_id=object_type_id
        ).aggregate(Max('highest'))["highest__max"]
        max = 0 if max is None else max
        return max

    @staticmethod
    def get_lowest_sell_price_multi(object_type_ids, structure):
        gen_key = lambda i: ("dao_lowest_sell_price_"+str(structure.pk)+"_{}").format(i)
        gen_value = lambda i: MarketPriceDAO.calculate_lowest_sell_price(structure=structure, object_type_id=i)
        return MarketPriceDAO._load_cached_range(
            object_type_ids,
            gen_key,
            gen_value
        )

    @staticmethod
    def get_lowest_sell_order_multi(object_type_ids, structure):
        gen_key = lambda i: ("dao_lowest_sell_order_"+str(structure.pk)+"_{}").format(i)
        gen_value = lambda i: MarketPriceDAO.calculate_lowest_sell_order(structure=structure, object_type_id=i)
        return MarketPriceDAO._load_cached_range(
            object_type_ids,
            gen_key,
            gen_value
        )

    @staticmethod
    def get_sell_volume_posted_multi(object_type_ids, structure):
        gen_key = lambda i:  ("dao_posted_order_volume_"+str(structure.pk)+"_{}").format(i)
        gen_value = lambda i: MarketPriceDAO.calculate_posted_volume(i, False, structure)
        return MarketPriceDAO._load_cached_range(
            object_type_ids,
            gen_key,
            gen_value
        )

    @staticmethod
    def get_avg_velocity30_multi(object_type_ids, region):
        gen_key = lambda i: ("dao_velocity_" + str(region.pk) + "_30_{}").format(i)
        gen_value = lambda i: MarketPriceDAO.calculate_avg_velocity_30day(i, region.pk)
        return MarketPriceDAO._load_cached_range(
            object_type_ids,
            gen_key,
            gen_value
        )

    @staticmethod
    def get_max_sell30_multi(object_type_ids, region):
        gen_key = lambda i: ("dao_max_sell_" + str(region.pk) + "_30_{}").format(i)
        gen_value = lambda i: MarketPriceDAO.calculate_max_sell_30day(i, region.pk)
        return MarketPriceDAO._load_cached_range(
            object_type_ids,
            gen_key,
            gen_value
        )

    @staticmethod
    def get_item_name_multi(object_type_ids, route):
        return ObjectType.get_cached_item_names_multi(object_type_ids)

    @staticmethod
    def get_dest_lowest_sell_multi(object_type_ids, route):
        return MarketPriceDAO.get_lowest_sell_price_multi(object_type_ids, route.destination_structure)

    @staticmethod
    def get_dest_lowest_order_multi(object_type_ids, route):
        return MarketPriceDAO.get_lowest_sell_order_multi(object_type_ids, route.destination_structure)

    @staticmethod
    def get_src_lowest_sell_multi(object_type_ids, route):
        return MarketPriceDAO.get_lowest_sell_price_multi(object_type_ids, route.source_structure)

    @staticmethod
    def get_freight_cost_total_multi(object_type_ids, route):
        item_volumes = ObjectType.get_cached_item_volumes_multi(object_type_ids)
        item_prices = MarketPriceDAO.get_lowest_sell_price_multi(object_type_ids, route.source_structure)

        zipped = zip(item_volumes, item_prices)

        return [
            route.cost_per_m3 * volume + (route.pct_collateral/100.0) * (price if price else 0)
            for volume, price in zipped
        ]

    @staticmethod
    def get_dest_sell_volume_posted_multi(object_type_ids, route):
        return MarketPriceDAO.get_sell_volume_posted_multi(object_type_ids, route.destination_structure)

    @staticmethod
    def get_listing_cost_multi(object_type_ids, route):
        # assuming user will post order at current lowest sell price
        item_prices = MarketPriceDAO.get_lowest_sell_price_multi(object_type_ids, route.destination_structure)
        return [
           (route.sales_tax/100.0) * p + (route.broker_fee/100.0) * p if p else None
            for p in item_prices
        ]

    @staticmethod
    def get_dest_velocity_multi(object_type_ids, route):
        return MarketPriceDAO.get_avg_velocity30_multi(object_type_ids, route.destination_structure.location.region)

    @staticmethod
    def get_dest_max_sell_past_30(object_type_ids, route):
        return MarketPriceDAO.get_max_sell30_multi(object_type_ids, route.destination_structure.location.region)

    @staticmethod
    def get_dest_depletion_estimate_multi(object_type_ids, route):
        velocity = MarketPriceDAO.get_dest_velocity_multi(object_type_ids, route)
        volume = MarketPriceDAO.get_dest_sell_volume_posted_multi(object_type_ids, route)
        zipped = zip(velocity, volume)
        return [
            volume / velocity if volume and velocity else 0 if velocity else None
            for velocity, volume in zipped
        ]

    @staticmethod
    def get_cogs_multi(object_type_ids, route):
        freight_costs = MarketPriceDAO.get_freight_cost_total_multi(object_type_ids, route)
        listing_costs = MarketPriceDAO.get_listing_cost_multi(object_type_ids, route)
        purchase_costs = MarketPriceDAO.get_src_lowest_sell_multi(object_type_ids, route)

        zipped = zip(freight_costs, listing_costs, purchase_costs)
        return [
            freight+listing+purchase if freight and listing and purchase else None
            for freight, listing, purchase in zipped
        ]

    @staticmethod
    def get_unit_profit_multi(object_type_ids, route):
        cogs = MarketPriceDAO.get_cogs_multi(object_type_ids, route)
        sell_price = MarketPriceDAO.get_dest_lowest_sell_multi(object_type_ids, route)
        zipped = zip(cogs, sell_price)
        return [
            sell - cost if sell and cost else None
            for cost, sell in zipped
        ]


    @staticmethod
    def get_projected_daily_profit_multi(object_type_ids, route):
        unit_profit = MarketPriceDAO.get_unit_profit_multi(object_type_ids, route)
        velocity = MarketPriceDAO.get_dest_velocity_multi(object_type_ids, route)
        zipped = zip(unit_profit, velocity)
        return [
            profit * vel if profit and vel else None
            for profit, vel in zipped
        ]

    @staticmethod
    def get_capital_efficiency_multi(object_type_ids, route):
        cogs = MarketPriceDAO.get_cogs_multi(object_type_ids, route)
        unit_profit = MarketPriceDAO.get_unit_profit_multi(object_type_ids, route)
        zipped = zip(unit_profit, cogs)
        return [
            (100.0 * unit_p / cog) if unit_p and cog else None for unit_p, cog in zipped
        ]

    @staticmethod
    def get_item_id_multi(object_type_ids, route):
        return object_type_ids

    @staticmethod
    def get_shopping_list_ids_multi(object_type_ids, route):
        lookup = ShoppingListItem.get_route_shopping_lookup(route)

        return [
            lookup[type_id].pk if type_id in lookup else None for type_id in object_type_ids
        ]

    @staticmethod
    def get_shopping_list_quantity_multi(object_type_ids, route):
        lookup = ShoppingListItem.get_route_shopping_lookup(route)

        return [
            lookup[type_id].quantity if type_id in lookup else 0 for type_id in object_type_ids
        ]

    @staticmethod
    def get_multi_bindings():
        return {
            MarketDataType.item_name: MarketPriceDAO.get_item_name_multi,
            MarketDataType.dest_volume_posted: MarketPriceDAO.get_dest_sell_volume_posted_multi,
            MarketDataType.dest_velocity: MarketPriceDAO.get_dest_velocity_multi,
            MarketDataType.dest_depletion_estimate: MarketPriceDAO.get_dest_depletion_estimate_multi,
            MarketDataType.dest_lowest_sell: MarketPriceDAO.get_dest_lowest_sell_multi,
            MarketDataType.src_lowest_sell: MarketPriceDAO.get_src_lowest_sell_multi,
            MarketDataType.freight_cost_total: MarketPriceDAO.get_freight_cost_total_multi,
            MarketDataType.listing_cost: MarketPriceDAO.get_listing_cost_multi,
            MarketDataType.cogs: MarketPriceDAO.get_cogs_multi,
            MarketDataType.unit_profit: MarketPriceDAO.get_unit_profit_multi,
            MarketDataType.capital_efficiency: MarketPriceDAO.get_capital_efficiency_multi,
            MarketDataType.projected_daily_profit: MarketPriceDAO.get_projected_daily_profit_multi,
            MarketDataType.item_id: MarketPriceDAO.get_item_id_multi,
            MarketDataType.shopping_list_id: MarketPriceDAO.get_shopping_list_ids_multi,
            MarketDataType.shopping_list_qty: MarketPriceDAO.get_shopping_list_quantity_multi,
            MarketDataType.dest_max_sell_past_30: MarketPriceDAO.get_dest_max_sell_past_30,
        }

