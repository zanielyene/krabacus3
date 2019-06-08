import time, logging
from conf.huey_queues import player_queue


import dateutil.parser
from datetime import timedelta

from eve_api.esi_client import EsiClient
from market.models import MarketOrder, PlayerOrderScanLog
from eve_api.models import Structure, EVEPlayerCharacter, ObjectType, EsiKey
from huey import crontab

from .util import get_characters_needing_update

from django.db.models import Q
from django.utils import timezone

logger=logging.getLogger(__name__)

player_orders_timedelta = timedelta(minutes=20)

@player_queue.periodic_task(crontab(minute='*/5'))
def enqueue_update_player_orders():
    logger.info("LAUNCH_TASK {}".format("enqueue_update_player_orders"))

    oldest_allowable_update = timezone.now() - player_orders_timedelta
    filter_statement = Q(orders_last_updated__lte=oldest_allowable_update) | Q(orders_last_updated__isnull=True)

    chars_with_valid_update_keys = get_characters_needing_update(
        filter_statement,
        "esi-markets.read_character_orders.v1"
    )

    logger.info("enqueueing {} player order update tasks".format(len(chars_with_valid_update_keys)))
    for char_id in chars_with_valid_update_keys:
        update_player_orders(char_id)

    logger.info("done enqueueing market order updates")


def _create_new_orders(character, orders):
    orders_to_commit = []
    logger.info("Creating {} orders for character {}".format(len(orders), character.pk))
    for order in orders:
        orders_to_commit.append(MarketOrder(
                ccp_id = order["order_id"],
                character = character,
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
            ))

    MarketOrder.objects.bulk_create(orders_to_commit)
    # populate cache fields
    MarketOrder.populate_cache_for_new_objects(orders_to_commit)
    logger.info("New orders committed & cache populated for character {}".format(character.pk))


@player_queue.task()
def update_player_orders(ccp_id):
    logger.info("LAUNCH_TASK {} {}".format("update_player_orders", ccp_id))
    with player_queue.lock_task('update-player-orders-{}'.format(ccp_id)):
        character = EVEPlayerCharacter.get_object(ccp_id)
        # double check to verify we actually need to scan this character right now
        oldest_allowable_update = timezone.now() - player_orders_timedelta
        if character.orders_last_updated and character.orders_last_updated > oldest_allowable_update:
            return

        scan_log = PlayerOrderScanLog(character = character)
        scan_log.save()
        client = EsiClient(authenticating_character=character)

        orders, _ = client.get("/v2/characters/{}/orders/".format(character.pk))
        order_ids = [o["order_id"] for o in orders]
        logger.info("Character {} has {} market orders".format(ccp_id, len(order_ids)))

        orders_ids_to_create = MarketOrder.set_order_owner(character, order_ids)
        logger.info("{} orders belonging to {} were not found in the database.".format(len(orders_ids_to_create), ccp_id))

        character.orders_last_updated = timezone.now()
        character.save()
        scan_log.scan_complete = timezone.now()
        scan_log.save()
    # do not create new orders. order discovery only happens when structures are scanned
    #orders_to_create = []
    #for order in orders:
    #    if order["order_id"] in orders_ids_to_create:
    #        orders_to_create.append(order)
    #_create_new_orders(character, orders_to_create)
