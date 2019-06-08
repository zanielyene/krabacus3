from django.db import models
import logging, requests
from eve_api.models import EVEPlayerCharacter, Structure
from eve_api.esi_client import EsiClient, EsiError
from django.db.utils import InternalError, IntegrityError
from django.core.cache import cache
import urllib

logger = logging.getLogger(__name__)


def structure_search(char_id, search_string):
    char = EVEPlayerCharacter.get_object(char_id)

    client = EsiClient(authenticating_character=char, raise_application_errors=False)
    logger.info("search string {}".format(search_string))

    search_param = urllib.parse.urlencode({"search":search_string})
    logger.info("search param {}".format(search_param))
    res, err = client.get("/v3/characters/{}/search/?categories=structure,station&language=en-us&{}&strict=false".format(char_id, search_param))
    if err == EsiError.EsiApplicationError:
        return []

    results = []
    if "structure" in res:
        if res["structure"]:
            Structure.load_citadels_async(res["structure"], client)
            results.extend(res["structure"])
    if "station" in res:
        if res["station"]:
            stations_to_load = []
            for station_id in res["station"]:
                if not Structure.exists(station_id):
                    stations_to_load.append(station_id)
                else:
                    results.append(station_id)
            Structure.load_stations_async(stations_to_load, client)
            results.extend(stations_to_load)
    return results
