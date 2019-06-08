import time, logging
from conf.huey_queues import history_queue


import dateutil.parser
from datetime import timedelta

from eve_api.esi_client import EsiClient
from market.models import TradingRoute, MarketHistoryScanLog, MarketPriceDAO, MarketHistory
from eve_api.models import Structure, EVEPlayerCharacter, ObjectType, Region

import dateutil.parser
from django.db.models import Q
from django.db import connection
from django.utils import timezone
from huey import crontab


from django.db import transaction

logger=logging.getLogger(__name__)

# ignore todays orders
@history_queue.periodic_task(crontab(minute=0, hour=9))
def enqueue_update_market_history():
    logger.info("LAUNCH_TASK {}".format("enqueue_update_market_history"))
    # for each region we have trading routes in
    source_regions = TradingRoute.objects.all().values_list('source_structure__location__region', flat=True)
    dest_regions = TradingRoute.objects.all().values_list('destination_structure__location__region', flat=True)

    regions = list(set(list(source_regions) + list(dest_regions)))
    #regions = Region.objects.all().values_list('ccp_id')

    logger.info("enqueueing market history updates for {} regions".format(len(regions)))
    for region_id in regions:
        update_region_market_history(region_id)


def _get_existing_region_entries(region_id, oldest_entry_days):
    existing_entries = MarketHistory.objects.filter(
        region_id=region_id,
        date__gte=(timezone.now() - timedelta(days=oldest_entry_days)).date()
        ).values_list('object_type_id', 'date')

    existing_entries_dict = {}
    for e in existing_entries:
        obj_id = e[0]
        entry_date = e[1]
        if obj_id in existing_entries_dict:
            existing_entries_dict[obj_id].append(entry_date)
        else:
            existing_entries_dict[obj_id] = [entry_date]
    return existing_entries_dict


@history_queue.task()
def update_region_market_history(region_id):
    logger.info("LAUNCH_TASK {} {}".format("update_region_market_history", region_id))
    with history_queue.lock_task('update-region-market-history-{}'.format(region_id)):
        logger.info("update_region_market_history {} LOCK ACQUIRED".format(region_id))

        # drop dbconn here
        logger.info("resetting django db connection for update_region_market_history {}".format(region_id))
        connection.connect()

        scan_log = MarketHistoryScanLog(region = Region.get_object(region_id))
        scan_log.save()

        items = ObjectType.get_all_tradeable_items()

        client = EsiClient(raise_application_errors=False)
        esi_url = "/v1/markets/{}/history/".format(region_id) + "?type_id={}"

        item_histories = client.get_multiple(esi_url, items)

        # check for items removed from the game/trading
        to_delete = []
        logger.info("Done pulling item market history, pruning unpublished items")
        for object_id, h in item_histories.items():
            if type(h) is dict:
                if "error" in h:
                    if h["error"] == 'Type not found!':
                        ObjectType.verify_object_exists(object_id, force=True)
                        object = ObjectType.get_object(object_id)
                        if not object.published or not object.market_group:
                            to_delete.append(object_id)
                            logger.info("Setting object_id {} to unpublished".format(object_id))
                    else:
                        msg = "receiving unrecognized application error from market query. object id {} error {}".format(object_id, h)
                        logger.error(msg)
                        raise Exception(msg)
                else:
                    logger.warning("dict-based item history detected {} {}".format(object_id, h))

        for i in to_delete:
            del item_histories[i]

        logger.info("Done pruneing unpublished items. Yanking existing markethistory entries out of the database")
        # grab existing entries
        existing_entries = _get_existing_region_entries(region_id, 30)

        logger.info("Done yanking old data. Building table of new data...")
        new_entries_to_commit = []
        new_entry_count = 0

        for object_id, history in item_histories.items():
            existing = existing_entries[object_id] if object_id in existing_entries else []
            # only use the last 31 days of history data (ccp sorts for us)
            history = history[-31:]
            new_entries = update_market_history_for_item(region_id, object_id, history, existing)
            new_entries_to_commit.extend(new_entries)
            new_entry_count += len(new_entries)

            if new_entry_count > 10000:
                # early commit
                logger.info("performing early commit of market history data")
                MarketHistory.objects.bulk_create(new_entries_to_commit)
                new_entries_to_commit = []
                new_entry_count = 0

        if new_entry_count > 0:
            logger.info("performing final market history data commit")
            MarketHistory.objects.bulk_create(new_entries_to_commit)

        logger.info("done creating history items, purging cache")
        MarketPriceDAO.purge_region_dao_cache(region_id, items)
        scan_log.scan_complete = timezone.now()
        scan_log.save()
        logger.info("market history cache purged. all done")


def update_market_history_for_item(region_id, object_id, history_entries, existing_entries):

    max_age = timedelta(days=30)
    today = timezone.now()
    ret = []
    for entry in history_entries:
        # ignore if today's date (gmt)
        date = dateutil.parser.parse(entry["date"]).date()
        if today.day == date.day and today.year == date.year and today.month == date.month:
            continue

        if date < (today - max_age).date():
            continue

        if date not in existing_entries:
            history = MarketHistory(
                object_type_id = object_id,
                date = date,
                average = entry["highest"],
                lowest = entry["lowest"],
                highest = entry["highest"],
                order_count = entry["order_count"],
                volume = entry["volume"],
                region_id = region_id
            )
            ret.append(history)

    return ret
