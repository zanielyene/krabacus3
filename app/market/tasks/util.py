import logging

from market.models import TradingRoute
from eve_api.models import  EVEPlayerCharacter,  EsiKey

from django.db.models import Q

logger = logging.getLogger(__name__)


def get_structures_we_have_keys_for():
    all_source_structures = TradingRoute.objects.filter(source_character_has_access=True).values_list('source_structure_id', flat=True)
    all_dest_structures = TradingRoute.objects.filter(destination_character_has_access=True).values_list('destination_structure_id', flat=True)
    structures_with_keys = []
    structures_with_keys.extend(all_source_structures)
    structures_with_keys.extend(all_dest_structures)
    return set(structures_with_keys)


def get_characters_needing_update(filter_statement, scope):

    # get characters that are a source or sink
    source_chars = TradingRoute.objects.filter(creator__subscription__active=True).values_list('source_character__pk', flat=True)
    dest_chars = TradingRoute.objects.filter(creator__subscription__active=True).values_list('destination_character__pk', flat=True)
    chars = list(set(source_chars).union(set(dest_chars)))

    logger.info("We have {} characters who we care about".format(len(chars)))

    chars_needing_update = EVEPlayerCharacter.objects.filter(
        (
            filter_statement
        ) &
        Q(key__use_key = True) &
        Q(pk__in=chars)
    ).values_list('pk', flat=True)

    logger.info("{} chars out of date  & ESI valid keys".format(len(chars_needing_update)))

    # check if these characters' keys allow us to grab market orders

    char_keys = EsiKey.objects.filter(
        Q(character_id__in=chars_needing_update) &
        Q(use_key=True)
    )

    chars_with_valid_update_keys = []
    for key in char_keys:
        if key.has_esi_scope(scope):
            chars_with_valid_update_keys.append(key.character.pk)

    logger.info("{} of the above characters have the correct scope on their key".format(len(chars_with_valid_update_keys)))
    return chars_with_valid_update_keys
