import logging
from django.utils import timezone
from eve_api.esi_client import EsiClient
from eve_api.models import EVEPlayerAlliance, EVEPlayerCharacter, CcpIdTypeResolver
from django.apps import apps

from .util import is_downtime
from django.core.cache import cache

logger=logging.getLogger(__name__)


def _get_cached_corp_affiliation(corporation_id):
    EVEPlayerCorporation_lazy = apps.get_model('eve_api', 'EVEPlayerCorporation')
    corp_affil_current = cache.get("corporation_affiliation_{}".format(corporation_id))

    # no cached corp affiliation has been set
    if corp_affil_current is None:
        corp = EVEPlayerCorporation_lazy.get_object(corporation_id)
        corp_affil_current = corp.alliance.pk if corp.alliance else None

    # we use zero as a placeholder for a corporation not being member of an alliance.
    # undo placeholder here
    if corp_affil_current is 0:
        corp_affil_current = None
    return corp_affil_current


def _set_cached_corp_affiliation(corporation_id, alliance_id):
    remapped_alliance_id = 0 if alliance_id is None else alliance_id
    cache.set("corporation_affiliation_{}".format(corporation_id), remapped_alliance_id, timeout=86400)
    return



def update_corporation_public_details(corporation_id, throttle_updates):
    """
    Updates a corporations public details including CEO, member count, affiliation.
    By passing throttle_updates=True, this task will only be fully executed once every hour.
    If you pass throttle_updates=False, this task will fully complete all its esi calls no matter what.
    :param corporation_id:
    :param throttle_updates:
    :return:
    """

    if throttle_updates:
        # do not add this key to EVEPlayerCorporation's post_save cache flush
        c = cache.get("corporation_details_update_throttled_{}".format(corporation_id))
        if c:
            return

    EVEPlayerCorporation_lazy = apps.get_model('eve_api', 'EVEPlayerCorporation')
    corporation = EVEPlayerCorporation_lazy.get_object(corporation_id)

    client = EsiClient()
    corp_details, _ = client.get("/v4/corporations/{}/".format(corporation_id))

    if corporation.alliance_id != corp_details.get("alliance_id"):
        if corp_details.get("alliance_id"):
            _ = EVEPlayerAlliance.get_object(corp_details["alliance_id"])
        corporation.alliance_id = corp_details.get("alliance_id")

    corporation.member_count = int(corp_details["member_count"])
    corporation.tax_rate = float(corp_details["tax_rate"])

    if not corporation.ceo_character or corporation.ceo_character.pk != corp_details["ceo_id"]:
        corporation.ceo_character = EVEPlayerCharacter.get_object(corp_details["ceo_id"])
    corporation.save()


    # we only set these once we're certain the update completed successfuly
    cache.set("corporation_details_update_throttled_{}".format(corporation_id), True, timeout=3600)
    _set_cached_corp_affiliation(corporation_id, corp_details.get("alliance_id"))



def set_corporation_affiliation(corporation_id, alliance_id):
    """
    Sets the specified corporation's alliance to the provided alliance id (or none, if specified).
    :param corporation_id:
    :param alliance_id:
    :return:
    """
    corp_affil_current = _get_cached_corp_affiliation(corporation_id)

    if corp_affil_current != alliance_id:
        # update all of the corporation's details
        update_corporation_public_details(corporation_id, throttle_updates=False)
    else:
        # make sure this is in cache
        _set_cached_corp_affiliation(corporation_id, alliance_id)


def provision_esi_corporation(corp_id, force=False):
    EVEPlayerCorporation_lazy = apps.get_model('eve_api', 'EVEPlayerCorporation')

    corp, created = EVEPlayerCorporation_lazy.objects.get_or_create(pk=corp_id)
    if not created and not force:
        return corp

    if force:
        logger.warning("forcing reload of corporation {}".format(corp_id))

    client = EsiClient()
    corp_data, _ = client.get("/v4/corporations/{}/".format(corp_id))

    corp.name = corp_data["name"]
    corp.ticker = corp_data["ticker"]
    #description = corp_data.get("description")
    #corp.description = description.decode('ascii','ignore').encode("ascii") if description else None
    #url = corp_data.get("url")
    #corp.url = url.decode('ascii','ignore').encode("ascii") if url else None
    corp.tax_rate = corp_data["tax_rate"]
    corp.member_count = corp_data["member_count"]
    # whoever made the corp model didnt use a bigint and i dont care enough to migrate it
    corp.shares = 0

    if "alliance_id" in corp_data:
        corp.alliance = EVEPlayerAlliance.get_object(corp_data["alliance_id"])

    corp.api_last_upated = timezone.now()
    corp.save()

    # Skip looking up the CEOs for NPC corps and ones with no CEO defined (dead corps)
    # this MUST happen after the corp is initially saved.

    if corp_id > 1000182 and int(corp_data['ceo_id']) > 1:
        corp.ceo_character = EVEPlayerCharacter.get_object(corp_data["ceo_id"])
        corp.save()

    CcpIdTypeResolver.add_type(corp_id, "corporation")
    return corp
