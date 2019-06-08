import logging
from conf.huey_queues import player_queue

from huey import crontab
import waffle
from datetime import timedelta

from market.models import TradingRoute, AssetEntry, AssetContainer, PlayerAssetsScanLog
from eve_api.models import Structure, EVEPlayerCharacter
from eve_api.tasks import get_character_assets

from django.db.models import Q
from django.db import transaction
from django.utils import timezone

from .util import get_characters_needing_update

logger=logging.getLogger(__name__)

player_assets_timedelta = timedelta(minutes=60)


def _is_container(asset):
    if not asset["type"].market_group:
        return False
    if asset["type"].market_group.parent_id == 379 and asset["is_singleton"]:
        return True
    else:
        return False


def _remove_invalid_assets(assets, valid_structure_ids = None):
    filtered_assets = []
    location_lookup = {}
    for a in assets:
        location_lookup[a["item_id"]] = a

    for a in assets:
        # remove items not in hangar or a container
        if a["location_flag"] != "Hangar" and a["location_flag"] != "Unlocked":
            continue

        # remove items that are not singleton
        if not _is_container(a) :
            if a["is_singleton"]:
                continue

        # if in container, make sure that container is a storage container and not asset safety or something
        if a["is_in_container"]:
            if not _is_container(location_lookup[a["location"].pk]):
                continue

        # remove bpcs
        if a["is_blueprint_copy"]:
            continue

        # remove unsellable items
        if not a["type"].market_group or not a["type"].published:
            continue

        # remove if not in a sanctioned structure
        if valid_structure_ids:
            if a["location"].root_location_id not in valid_structure_ids:
                continue

            filtered_assets.append(a)

    # rebuild location table now we've removed undesired items
    location_lookup = [asset["item_id"] for asset in filtered_assets if _is_container(asset)]


    # strip out container'ed assets whose container was already removed
    ret_assets = [asset for asset in filtered_assets if not asset["is_in_container"] or (asset["is_in_container"] and asset["location"].pk in location_lookup)]

    return ret_assets


def _split_assets_and_containers(assets):
    ret_assets = []
    containers = []

    for a in assets:
        if _is_container(a):
            containers.append(a)
        else:
            ret_assets.append(a)

    return ret_assets, containers


def _get_player_assets_and_containers(char):
    routes = TradingRoute.objects.filter(
        destination_character = char
    )

    valid_structures = [route.destination_structure.pk for route in routes]

    unfiltered_assets = get_character_assets(char.pk)

    filtered_assets = _remove_invalid_assets(unfiltered_assets, valid_structures)

    assets, containers = _split_assets_and_containers(filtered_assets)

    # check for containers that were erroneously removed
    containers_lookup = [c["item_id"] for c in containers]
    for a in assets:
        if a["is_in_container"]:
            if a["location"].pk not in containers_lookup:
                removed_container = None
                for c in unfiltered_assets:
                    if c["item_id"] == a["location"].pk:
                        removed_container = c
                        break
                logger.error("Container was erroneously removed. child item: {} src container: {}".format(a, removed_container))

    return assets, containers


@player_queue.task()
def update_player_assets(character_id):
    logger.info("LAUNCH TASK update_player_assets {}".format(character_id))
    with player_queue.lock_task('update-player-assets-{}'.format(character_id)):
        char = EVEPlayerCharacter.get_object(character_id)

        # double check to verify we actually need to scan this character right now
        oldest_allowable_update = timezone.now() - player_assets_timedelta
        if char.assets_last_updated and char.assets_last_updated > oldest_allowable_update:
            logger.warning("{} was queued for assets update quickly over a given interval. killing followup task".format(character_id))
            return

        scan_log = PlayerAssetsScanLog.start_scan_log(char)

        assets, containers = _get_player_assets_and_containers(char)

        # extract hashes to figure out current configuration
        current_assets_hash = AssetEntry.generate_hash(character_id)
        new_assets_hash = AssetEntry.generate_has_from_list(assets)
        force = False

        if new_assets_hash != current_assets_hash or force:
            logger.info("Assets hash changed for {}, updating assets".format(character_id))

            with transaction.atomic():
                AssetEntry.objects.filter(character_id=character_id).delete()
                AssetContainer.objects.filter(character_id=character_id).delete()

                container_objs = []
                asset_objs = []

                for c in containers:
                    container_objs.append(
                        AssetContainer(
                        ccp_id = c["item_id"],
                        character = char,
                        structure = Structure.get_object(c["location"].root_location_id, char.pk),
                        name = c["name"]
                    ))
                AssetContainer.objects.bulk_create(container_objs)

                for a in assets:
                    asset_objs.append(
                        AssetEntry(
                            ccp_id=a["item_id"],
                            character=char,
                            structure=Structure.get_object(a["location"].root_location_id, char.pk),
                            container_id = None if not a["is_in_container"] else a["location"].pk,
                            quantity = a["quantity"],
                            object_type = a["type"]
                        )
                    )

                AssetEntry.objects.bulk_create(asset_objs)

        char.assets_last_updated = timezone.now()
        char.save()

        scan_log.stop_scan_log()

    logger.info("COMPLETE TASK update_player_assets {}".format(character_id))
    return


@player_queue.periodic_task(crontab(minute='*/5'))
def enqueue_update_player_assets():
    if waffle.switch_is_active('enable-player-asset-scans'):
        logger.info("LAUNCH_TASK {}".format("enqueue_update_player_assets"))

        oldest_allowable_update = timezone.now() - player_assets_timedelta
        filter_statement = Q(assets_last_updated__lte=oldest_allowable_update) | Q(assets_last_updated__isnull=True)

        chars_with_valid_update_keys = get_characters_needing_update(
            filter_statement,
            "esi-assets.read_assets.v1"
        )

        logger.info("enqueueing {} player asset update tasks".format(len(chars_with_valid_update_keys)))
        for char_id in chars_with_valid_update_keys:
            update_player_assets(char_id)

        logger.info("done enqueueing player asset updates")
