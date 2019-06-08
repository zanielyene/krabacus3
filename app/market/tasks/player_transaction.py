import  logging
from conf.huey_queues import player_queue

import dateutil.parser
from datetime import timedelta

from eve_api.esi_client import EsiClient
from market.models import TradingRoute, PlayerTransactionScanLog, PlayerTransaction
from eve_api.models import Structure, EVEPlayerCharacter, ObjectType
from huey import crontab

from django.db.models import Q
from django.utils import timezone

from .util import get_characters_needing_update

logger=logging.getLogger(__name__)

player_transactions_timedelta = timedelta(minutes=60)

@player_queue.periodic_task(crontab(minute='*/5'))
def enqueue_update_player_transactions():
    logger.info("LAUNCH_TASK {}".format("enqueue_update_player_transactions"))

    oldest_allowable_update = timezone.now() - player_transactions_timedelta
    filter_statement = Q(transactions_last_updated__lte=oldest_allowable_update) | Q(transactions_last_updated__isnull=True)

    chars_with_valid_update_keys = get_characters_needing_update(
        filter_statement,
        "esi-wallet.read_character_wallet.v1"
    )
    logger.info("{} characters have valid transactions keys".format(len(chars_with_valid_update_keys)))



    logger.info("enqueueing {} player transaction update tasks".format(len(chars_with_valid_update_keys)))
    for char_id in chars_with_valid_update_keys:
        update_player_transactions(char_id)

    logger.info("done enqueueing market transaction updates")


def _get_transactions(client, character):
    #oldest_txn=PlayerTransaction.objects.filter(
    #    character=character
    #).order_by('ccp_id').\
    #    values_list('ccp_id', flat=True).\
    #    first()
    oldest_txn = None

    transactions=[]
    while True:
        if oldest_txn is None:
            raw_txns, _ = client.get("/v1/characters/{}/wallet/transactions/".format(character.pk))
        else:
            raw_txns, _ = client.get("/v1/characters/{}/wallet/transactions/?from_id={}".format(character.pk, oldest_txn-1))

        if not raw_txns:
            break

        oldest_txn=min(raw_txns, key=lambda t: t["transaction_id"])["transaction_id"]
        transactions.extend(raw_txns)

    return transactions


def _verify_transaction_models_exist(transactions, character):
    for transaction in transactions:
        Structure.verify_object_exists(transaction["location_id"], character.pk)
        ObjectType.verify_object_exists(transaction["type_id"])


@player_queue.task()
def update_player_transactions(ccp_id):
    logger.info("LAUNCH_TASK {} {}".format("update_player_transactions", ccp_id))
    with player_queue.lock_task('update-player-transactions-{}'.format(ccp_id)):
        character = EVEPlayerCharacter.get_object(ccp_id)

        # double check to verify we actually need to scan this character right now
        oldest_allowable_update = timezone.now() - player_transactions_timedelta
        if character.transactions_last_updated and character.transactions_last_updated > oldest_allowable_update:
            logger.warning(
                "{} was queued for transactions update quickly over a given interval. killing followup task".format(
                    ccp_id))
            return

        scan_log = PlayerTransactionScanLog(character=character)
        scan_log.save()

        client = EsiClient(authenticating_character=character)

        transactions = _get_transactions(client, character)

        _verify_transaction_models_exist(transactions, character)

        txn_models = []
        logger.info("scanning {} transactions for {}".format(len(transactions), ccp_id))
        transaction_ids_being_added = []
        for t in transactions:
            # check if t exists
            exists = PlayerTransaction.exists(t["transaction_id"])
            if not exists and t["transaction_id"] not in transaction_ids_being_added:
                transaction_ids_being_added.append(t["transaction_id"])
                txn_models.append(PlayerTransaction(
                    character=character,
                    ccp_id=t["transaction_id"],
                    client_id=t["client_id"],
                    timestamp=dateutil.parser.parse(t["date"]),
                    is_buy=t["is_buy"],
                    is_personal=t["is_personal"],
                    journal_ref_id=t["journal_ref_id"],
                    location_id=t["location_id"],
                    quantity=t["quantity"],
                    object_type_id=t["type_id"],
                    unit_price=t["unit_price"],
                    quantity_without_known_source=t["quantity"],
                    quantity_without_known_destination=t["quantity"]
                ))

        logger.info("creating {} transactions for {}".format(len(txn_models), ccp_id))
        PlayerTransaction.objects.bulk_create(txn_models)

        trading_routes = TradingRoute.objects.filter(Q(source_character=character) | Q(destination_character=character))

        source_structures = trading_routes.filter(source_character=character).values_list("source_structure_id", flat=True)
        destination_structures = trading_routes.filter(destination_character=character).values_list("destination_structure_id", flat=True)

        #structure_ids = list(set(source_structures).union(set(destination_structures)))
        structure_ids = list(set(destination_structures))

        # maybe log n this later? or just remove it and always trigger a scan
        trigger_transaction_scan = True

        if trigger_transaction_scan:
            logger.info("trigger transaction scan for {}".format(character.pk))
            transactions_needing_link = PlayerTransaction.objects.filter(
                location_id__in=structure_ids,
                quantity_without_known_source__gt=0,
                is_buy=False,
                character = character
            )
            logger.info("checking {} transactions for linkages for {}".format(len(transactions_needing_link), character.pk))
            for t in transactions_needing_link:
                t.link_transactions()
            logger.info("Done checking for linkages")

        character.transactions_last_updated = timezone.now()
        character.save()

        scan_log.scan_complete = timezone.now()
        scan_log.save()

        # if any new transactions are in a source/dest structure
        # dest_transactions = <>.where destination_quantity_unaccounted != 0
        #       and object_type in route's import list
        # for each dest_transaction
        #       call search_for_source_transactions
        #            create TransactionLinkage

