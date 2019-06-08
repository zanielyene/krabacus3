


import time, logging
from conf.huey_queues import general_queue

from eve_api.esi_client import EsiClient, EsiError
from eve_api.models import EVEPlayerCharacter, Structure, EsiKey

from market.models import TradingRoute

logger=logging.getLogger(__name__)

# todo maybe: run this using a last_updated field instead of EVERYONE EVERYTIME
# todo: run every 24h
@general_queue.task()
def enqueue_update_structure_access():
    logger.info("LAUNCH_TASK {}".format("enqueue_update_structure_access"))
    active_routes = TradingRoute.objects.all()
    logger.info("Starting enqueue task for {} trade routes".format(len(active_routes)))
    for route in active_routes:
        update_structure_access(route.pk)
    return

def _does_character_have_structure_access(character_id, structure_id):
    has_access = True

    # is this a station?
    if structure_id >= 60000000 and structure_id <= 61000000:
        return True

    has_key = EsiKey.does_character_have_key(character_id)
    if not has_key:
        logger.info("Character {} no longer has access to structure {} due to a dead ESI key".format(character_id,structure_id))
        has_access=False
    else:
        # check if we can query the structure using this character
        char = EVEPlayerCharacter.get_object(character_id)
        client = EsiClient(authenticating_character=char, raise_application_errors=False, log_application_errors=False)
        res, err = client.get("/v2/universe/structures/{}/".format(structure_id))
        if err == EsiError.EsiApplicationError:
            logger.info("Character {} no longer has access to structure {} due to ESIApplicationError".format(character_id, structure_id))
            has_access = False
        if err == EsiError.InvalidRefreshToken:
            logger.info("Character {} no longer has access to structure {} due to newly dead ESI key".format(character_id, structure_id))
            has_access = False
    return has_access


@general_queue.task()
def update_structure_access(route_id):
    """
    Updates the route's structure access
    :return:
    """
    logger.info("LAUNCH_TASK {} {}".format("update_structure_access", route_id))
    route = TradingRoute.objects.get(pk=route_id)

    source_char_has_access = _does_character_have_structure_access(
        route.source_character.pk,
        route.source_structure.pk
    )
    dest_char_has_access = _does_character_have_structure_access(
        route.source_character.pk,
        route.destination_structure.pk
    )

    if route.source_character_has_access != source_char_has_access \
        or route.destination_character_has_access != dest_char_has_access:
        logger.info("It looks like this route's trading access changed. Route ID {}".format(route.pk))

        route.source_character_has_access = source_char_has_access
        route.destination_character_has_access = dest_char_has_access
        route.save()