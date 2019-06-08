import logging
from django.db.utils import InternalError

from eve_api.esi_client import EsiClient
from eve_api.models import EVEPlayerCharacter, EVEPlayerCorporation, ObjectType, Structure, EVEPlayerAlliance, System, CcpIdTypeResolver
from eve_api.tasks import util

logger=logging.getLogger(__name__)


def resolve_extra_info_object(character, key, value):
    if key == "structure_id" or key == "station_id":
        Structure.verify_object_exists(value, character.pk)
    elif key == "type_id":
        ObjectType.verify_object_exists(value)
    elif key == "character_id":
        # fix inaccurate CCP data
        # CCP uses character_id as a catch-all key for special extra_info types that aren't defined.
        actual_type = CcpIdTypeResolver.get_id_type(value)
        if actual_type == "character":
            EVEPlayerCharacter.verify_object_exists(value)
        else:
            logger.error("getting incorrect character_id journal thing for type id %s actual_Type: %s" % (value, actual_type))
            return None,None
    elif key == "corporation_id":
        EVEPlayerCorporation.verify_object_exists(value)
    elif key == "alliance_id":
        EVEPlayerAlliance.verify_object_exists(value)
    elif key == "system_id":
        System.verify_object_exists(value)
    elif key == "market_transaction_id" or key == "industry_job_id" or key == "contract_id" or key == "planet_id" or key == "eve_system":
        #idgaf
        pass
    else:
        raise Exception("ccp returning some fancy new key object? %s %s" % (key,value) )

    return (key,value)


def verify_journal_entry(entry, character):
    if "first_party_id" in entry:
        # no more first_party_type!
        first_party_type = CcpIdTypeResolver.get_id_type( entry["first_party_id"])
        if first_party_type is None:
            raise Exception("Unknown first party type %s found in char report of %s" % (entry["first_party_id"], character.name))
        entry["first_party_type"] = first_party_type
        util.verify_generic_object_exists(entry["first_party_type"], entry["first_party_id"])
    if "second_party_id" in entry:
        # no more second_party_type!
        second_party_type = CcpIdTypeResolver.get_id_type( entry["second_party_id"])
        if second_party_type is None:
            raise Exception("Unknown second party type %s found in char report of %s" % (entry["first_party_id"], character.name))
        entry["second_party_type"] = second_party_type
        util.verify_generic_object_exists(entry["second_party_type"], entry["second_party_id"])

    if "context_id" in entry and "context_id_type" in entry:
        new_key, new_value = resolve_extra_info_object(character, entry["context_id_type"], entry["context_id"])
        entry["context_id"] = new_value
        entry["context_id_type"] = new_key
    else:
        entry["context_id_type"] = None
        entry["context_id"] = None

    return entry


def get_character_journal(character_ccp_id, page = 1, page_limit=5):
    """

    :param self:
    :param character_ccp_id:
    :param oldest_entry:
    :param page_limit:
    :return:
    """
    character = EVEPlayerCharacter.get_object(character_ccp_id)
    if not character.has_esi_scope('esi-wallet.read_character_wallet.v1'):
        return None
        
    client = EsiClient(authenticating_character=character)

    journal_entries, _ = client.get("/v4/characters/%s/wallet/journal/?page=%s" % (character_ccp_id,page))

    formatted_entries = []
    for entry in journal_entries:
        e = verify_journal_entry(entry, character)
        formatted_entries.append(e)

    # pagination logic
    if formatted_entries and page <= page_limit:
        older_entries = get_character_journal(
            character_ccp_id = character_ccp_id,
            page = page + 1,
            page_limit = page_limit
        )
    else:
        older_entries = []
    return journal_entries + older_entries