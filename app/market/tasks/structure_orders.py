import logging
from conf.huey_queues import general_queue


import dateutil.parser
from datetime import timedelta

from eve_api.esi_client import EsiClient
from .util import get_structures_we_have_keys_for
from market.models import TradingRoute, MarketOrder, MarketPriceDAO, StructureMarketScanLog
from eve_api.models import Structure, EVEPlayerCharacter, ObjectType
from huey import crontab
from django.conf import settings

from django.db.models import Q
from django.utils import timezone

from django.db import transaction

logger=logging.getLogger(__name__)


def _get_key_for_structure(structure_id):
    all_source_chars =  TradingRoute.objects.filter(
        source_character_has_access=True,
        source_structure_id = structure_id
    ).values_list('source_character', flat=True)
    all_dest_chars = TradingRoute.objects.filter(
        destination_character_has_access=True,
        destination_structure_id = structure_id
    ).values_list('destination_character', flat=True)

    all_structure_chars = list(set(list(all_source_chars) + list(all_dest_chars)))

    retry_count = -1
    for char in all_structure_chars:
        retry_count += 1
        logger.info("The following character is yielded for structure {}, {}. Retry count: {}".format(structure_id, char, retry_count))
        yield EVEPlayerCharacter.get_object(char)


def _get_station_orders(station_id):
    client = EsiClient()
    station = Structure.get_object(station_id, origin_character_id=None)

    results = client.get_multiple_paginated("/v1/markets/"+str(station.location.region.pk)+"/orders/")

    # filter out orders not in our target station
    filtered_orders = []
    for order in results:
        if order["location_id"] == station_id:
            filtered_orders.append(order)
    return filtered_orders


def _get_citadel_orders(structure_id, auth_char):
    client = EsiClient(authenticating_character=auth_char)
    results = client.get_multiple_paginated("/v1/markets/structures/"+str(structure_id)+"/")
    return results


def _get_orders(structure_id, auth_character):
    if structure_id >= 60000000 and structure_id <= 61000000:
        return _get_station_orders(structure_id)
    else:
        return _get_citadel_orders(structure_id, auth_character)


def _prune_dead_database_orders(structure_id, orders):
    # extract order_id from orders
    order_ids = [o["order_id"] for o in orders]

    dead_orders = MarketOrder.objects.filter(location_id=structure_id, order_active=True).exclude(ccp_id__in=order_ids)

    # we have to grab this stuff before we set order_active=False
    object_ids_impacted = set()
    dead_order_object_ids = dead_orders.values_list('object_type_id', flat=True)
    object_ids_impacted.update(dead_order_object_ids)

    logger.info("{} dead orders pruned".format(dead_orders.count()))
    dead_orders.update(order_active=False)
    # dead_orders is empty after this. do not use it. funny side effect from using .update instead of .save

    return list(object_ids_impacted)


def _insert_bulk_orders(orders):
    MarketOrder.objects.bulk_create(orders)
    # populate cache fields
    MarketOrder.populate_cache_for_new_objects(orders)


def _insert_new_db_orders(structure_id, orders):
    orders_to_create = []
    total_ctr = 0
    group_ctr = 0

    order_ids = [o["order_id"] for o in orders]

    logger.info("Processing {} orders retreived from ESI".format(len(order_ids)))

    already_existing_orders = \
        set(
            MarketOrder.objects.filter(
                location_id=structure_id,
                order_active=True,
                ccp_id__in=order_ids
            ).values_list('ccp_id', flat=True)
        )

    orders_to_add = set(order_ids).difference(already_existing_orders)

    # check for orders that were falsely inactivated
    orders_to_reactivate = \
        MarketOrder.objects.filter(
            location_id=structure_id,
            order_active=False,
            ccp_id__in=orders_to_add
        )

    # this is what gets returned
    object_ids_updated = set()

    if orders_to_reactivate:
        logger.info("{} orders were set to inactive that are actually still alive. Reactivating.".format(len(orders_to_reactivate)))

        orders_to_add = orders_to_add.difference(orders_to_reactivate.values_list('ccp_id', flat=True))

        # save all the object_ids impacted by reactivation
        object_ids_reactivated = orders_to_reactivate.values_list('object_type_id', flat=True)
        object_ids_updated.update(object_ids_reactivated)


        orders_to_reactivate.update(order_active=True)
        # do not use this variable again, .update vs .save shennagians

    for order in orders:
        if order["order_id"] in orders_to_add:
            # save object_id impacted by new order
            object_ids_updated.add(order["type_id"])

            # create order
            o = MarketOrder(
                ccp_id = order["order_id"],
                duration = order["duration"],
                is_buy_order = order["is_buy_order"],
                issued = dateutil.parser.parse(order["issued"]),
                location = Structure.get_object(order["location_id"], None),
                min_volume = order["min_volume"],
                price = order["price"],
                range = order["range"],
                object_type = ObjectType.get_object(order["type_id"]),
                volume_remain = order["volume_remain"],
                volume_total = order["volume_total"]
            )
            orders_to_create.append(o)
            total_ctr += 1
            group_ctr += 1

            if group_ctr >= 10000:
                logger.info("10000 objects to be committed, running bulk create early")
                _insert_bulk_orders(orders_to_create)
                logger.info("commit completed")
                group_ctr = 0
                orders_to_create = []

    if group_ctr:
        _insert_bulk_orders(orders_to_create)

    logger.info("{} new market orders inserted into db".format(total_ctr))
    return list(object_ids_updated)


def _update_db_order_details(orders):
    counter = 0
    orders_to_modify = {}

    logger.info("Trying to grab order prices & volume from cache")
    prices, volumes = MarketOrder.get_order_prices_and_volume(orders)
    logger.info("Prices & volumes loaded, figuring out what needs updating...")

    for order in orders:
        stored_price = prices[order["order_id"]]
        stored_vol_remain = volumes[order["order_id"]]

        if stored_price != order["price"] or stored_vol_remain != order["volume_remain"]:
            orders_to_modify[order["order_id"]] = order

    order_objects_to_modify = MarketOrder.objects.filter(ccp_id__in = orders_to_modify.keys())

    # this is what we're returning
    modified_object_ids = set()

    logger.info("Beginning massive transaction to update order details")
    with transaction.atomic():
        for order_obj in order_objects_to_modify:
            order_data = orders_to_modify[order_obj.pk]
            modified_object_ids.add(order_data["type_id"])

            order_obj.price = order_data["price"]
            order_obj.volume_remain = order_data["volume_remain"]
            order_obj.issued = dateutil.parser.parse(order_data["issued"])
            order_obj.save()
            counter += 1
    logger.info("{} market orders had their details updated".format(counter))
    return list(modified_object_ids)


def _update_orders_database(structure_id, orders):
    object_ids_updated = []
    # create new orders we dont have in the db
    object_ids_updated.extend(_insert_new_db_orders(structure_id, orders))

    # prune orders that arent around anymore
    object_ids_updated.extend(_prune_dead_database_orders(structure_id, orders))

    # update orders whose volume_remain has changed
    # update orders whose price has changed
    object_ids_updated.extend(_update_db_order_details(orders))

    # purge dao of object_ids_updated
    object_ids_updated = set(object_ids_updated)
    logger.info("total of {} object types need cache purged for structure {}".format(len(object_ids_updated), structure_id))
    MarketPriceDAO.purge_structure_price_cache(structure_id, object_ids_updated)


@general_queue.task()
def update_structure_orders(structure_id):
    with general_queue.lock_task('update-structure-orders-{}'.format(structure_id)):
        logger.info("LAUNCH_TASK {} {}".format("update_structure_orders", structure_id))
        structure = Structure.get_object(structure_id, None)
        scan_log = StructureMarketScanLog(structure = structure)
        scan_log.save()

        key_gen = _get_key_for_structure(structure_id)

        orders = []
        for character in key_gen:
            try:
                orders = _get_orders(structure_id, character)
                break
            except Exception as e:
                # generic catch all because there's so many things that can go wrong
                logger.warning("Failed to retrieve market data for {} using character {}. Error: {}".format(structure_id, character, e))
                if settings.DEBUG:
                    raise e
                continue
        logger.info("orders downloaded successfully for structure {}".format(structure_id))

        # update db
        _update_orders_database(structure_id,orders)
        logger.info("done updating structure {} orders".format(structure_id))
        s = Structure.get_object(structure_id, None)
        s.market_last_updated = timezone.now()

        s.market_data_expires = timezone.now() + timedelta(minutes=5)
        s.save()
        scan_log.scan_complete = timezone.now()
        scan_log.save()


def _get_out_of_date_structures():
    return set(
            Structure.objects.filter(
            Q(market_last_updated__isnull=True)
            | Q(market_data_expires__lte=timezone.now())
        ).values_list('ccp_id', flat=True)
    )


@general_queue.periodic_task(crontab(minute='*/5'))
def enqueue_update_structure_orders():
    logger.info("LAUNCH_TASK {}".format("enqueue_update_structure_orders"))
    out_of_date_structures = _get_out_of_date_structures()
    structures_with_keys = get_structures_we_have_keys_for()

    structures_to_update = list(out_of_date_structures.intersection(structures_with_keys))


    logger.info("{} structures queued for order updating".format(len(structures_to_update)))

    for s in structures_to_update:
        f = update_structure_orders.s(s)
        general_queue.enqueue(f)