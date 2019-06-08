import logging
from django.db.utils import InternalError

from eve_api.esi_client import EsiClient
from eve_api.models import EVEPlayerCharacter, EVEPlayerCorporation, Structure, ObjectType, CcpIdTypeResolver
from . import util
logger = logging.getLogger(__name__)


def extract_transaction(character, transaction):
    # CCP doesnt tell us what the client is, so try to resolve it ourselves
    client_type = CcpIdTypeResolver.get_id_type(transaction["client_id"])

    util.verify_generic_object_exists(client_type, transaction["client_id"])

    Structure.verify_object_exists(transaction["location_id"], character.pk)
    type_obj = ObjectType.get_object(transaction["type_id"])

    return {
        "client_type" : client_type,
        "transaction_id": transaction["transaction_id"],
        "date": transaction["date"],
        "location_id": transaction["location_id"],
        "type": type_obj,
        "unit_price": transaction["unit_price"],
        "quantity": transaction["quantity"],
        "client_id": transaction["client_id"],
        "is_buy": transaction["is_buy"],
        "is_personal": transaction["is_personal"],
        "journal_ref_id": transaction["journal_ref_id"]
    }


def get_character_transactions(character_ccp_id, oldest_entry=None, page=0):
    character = EVEPlayerCharacter.get_object(character_ccp_id)
    
    if not character.has_esi_scope('esi-wallet.read_character_wallet.v1'):
        return None
    
    client = EsiClient(authenticating_character=character)

    if oldest_entry is None:
        transaction_entries, _ = client.get("/v1/characters/%s/wallet/transactions/" % character_ccp_id)
    else:
        transaction_entries, _ = client.get("/v1/characters/%s/wallet/transactions/?from_id=%s" % (character_ccp_id,oldest_entry))

    oldest_transaction_entry = -1
    transactions = []
    for entry in transaction_entries:
        # keep track of the oldest transaction entry we received for pagination
        if entry["transaction_id"] < oldest_transaction_entry or oldest_transaction_entry == -1:
            oldest_transaction_entry = entry["transaction_id"]

        transactions.append(extract_transaction(character, entry))

    # pagination logic
    if oldest_transaction_entry != -1 and page < 5:
        prev_transactions = get_character_transactions(
            character_ccp_id = character_ccp_id,
            oldest_entry = oldest_transaction_entry-1,
            page=page+1
        )
    else:
        prev_transactions = []
    return transactions + prev_transactions





