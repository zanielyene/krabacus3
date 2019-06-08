import logging
from django.db.utils import InternalError

from eve_api.esi_client import EsiClient
from eve_api.models import EVEPlayerCharacter
from eve_api.models import Structure, System, CcpIdTypeResolver

logger=logging.getLogger(__name__)


def get_character_location(char_id):
    char = EVEPlayerCharacter.get_object(char_id)
    if not char.has_esi_scope('esi-location.read_location.v1'):
        return None
        
    client = EsiClient(authenticating_character=char)

    location, _ = client.get("/v1/characters/%s/location/" % char.pk)
    system_id = location["solar_system_id"]

    actual_type = CcpIdTypeResolver.get_id_type(system_id)

    # fix for CCP-side bug
    if actual_type != "system":
        structure_id = system_id
        structure = Structure.get_object(structure_id, char.pk)
        system = structure.location.system if structure.location else None
    else:
        system = System.get_object(system_id)

        # both structures and stations can be handled by structure.getobject
        if "structure_id" in location:
            structure = Structure.get_object(location["structure_id"], char.pk)
        elif "station_id" in location:
            structure = Structure.get_object(location["station_id"], char.pk)
        else:
            structure = None

    return {
        "system": system,
        "structure": structure
    }



