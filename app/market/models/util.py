import logging

from market.models import TradingRoute
from eve_api.models import  EVEPlayerCharacter,  EsiKey

from django.db.models import Q

logger = logging.getLogger(__name__)

# dupe code lol
def get_structures_we_have_keys_for():
    all_source_structures = TradingRoute.objects.filter(source_character_has_access=True).values_list('source_structure_id', flat=True)
    all_dest_structures = TradingRoute.objects.filter(destination_character_has_access=True).values_list('destination_structure_id', flat=True)
    structures_with_keys = []
    structures_with_keys.extend(all_source_structures)
    structures_with_keys.extend(all_dest_structures)
    return set(structures_with_keys)