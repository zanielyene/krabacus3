import logging

import requests
from django.db.utils import InternalError

from eve_api.esi_client import EsiClient
from eve_api.models import EVEPlayerCharacter

logger = logging.getLogger(__name__)


def get_character_balance(character_ccp_id):
    """
    Creates a new snapshot of the given character's wallet balance.
    :param self:
    :param character_ccp_id:
    :return:
    """
    character = EVEPlayerCharacter.objects.get(pk=character_ccp_id)
    if not character.has_esi_scope('esi-wallet.read_character_wallet.v1'):
        return None

    client = EsiClient(authenticating_character=character)
    balance, _ = client.get("/v1/characters/%s/wallet/" % character_ccp_id)

    return balance
