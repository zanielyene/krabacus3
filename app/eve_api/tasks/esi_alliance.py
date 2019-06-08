import logging

import requests
from django.db.utils import InternalError
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Q

from eve_api.esi_client import EsiClient
from eve_api.tasks.util import is_downtime
from eve_api.models import EVEPlayerCorporation, EVEPlayerAlliance, EVEPlayerCharacter, CcpIdTypeResolver
import dateutil.parser

logger=logging.getLogger(__name__)


def import_alliance_details():
    """
    Imports all in-game alliances and links their related corporations

    """
    client = EsiClient()
    # for some reason, calls to the alliances endpoints returns TUPLES. yes, tuples. WITH ONE ELEMENT IN THEM
    alliances, _ = client.get("/v1/alliances/")

    for alliance_id in alliances:
        if not EVEPlayerAlliance.objects.filter(pk=alliance_id).exists():
            provision_esi_alliance(alliance_id)

        update_alliance_corporations.delay(alliance_id)
    return



def queue_update_alliance_details(batch_size=200, update_interval_hours=7*24):
    if is_downtime():
        return
    delta = timedelta(hours=update_interval_hours)

    alliances_to_update = EVEPlayerAlliance.objects.filter(
            Q(api_last_updated__isnull = True) |
            Q(api_last_updated__lt = (timezone.now() - delta))
        )
    alliances_to_update = alliances_to_update[:batch_size]
    for alliance in alliances_to_update:
        update_alliance_corporations.delay(alliance_id = alliance.pk)
    return



def update_alliance_corporations(alliance_id):
    client = EsiClient()
    alliance_corporations, _ = client.get("/v1/alliances/%s/corporations/" % alliance_id)
    alliance_data, _ = client.get("/v3/alliances/%s/" % alliance_id)

    allobj = EVEPlayerAlliance.objects.get(pk=alliance_id)
    if "executor_corporation_id" in alliance_data:
        allobj.executor = EVEPlayerCorporation.get_object(alliance_data["executor_corporation_id"])
    allobj.api_last_updated = timezone.now()
    allobj.save()

    EVEPlayerCorporation.objects.filter(id__in=alliance_corporations).update(alliance=allobj)
    EVEPlayerCorporation.objects.filter(alliance=allobj).exclude(id__in=alliance_corporations).update(alliance=None)

    # Import any corps missing from DB
    importlist = set(alliance_corporations) - set(
        EVEPlayerCorporation.objects.filter(id__in=alliance_corporations).values_list('id', flat=True))
    from eve_api.tasks.esi_corporation import provision_esi_corporation
    for id in importlist:
        provision_esi_corporation.delay(id)
    return


def provision_esi_alliance(alliance_id):
    alliance, created = EVEPlayerAlliance.objects.get_or_create(pk=alliance_id)
    if not created:
        return alliance

    client = EsiClient()
    alliance_data, _ = client.get("/v3/alliances/%s/" % alliance_id)

    alliance.name = alliance_data["name"]
    alliance.ticker = alliance_data["ticker"]
    alliance.date_founded = dateutil.parser.parse(alliance_data["date_founded"])

    if "executor_corporation_id" in alliance_data:
        alliance.executor = EVEPlayerCorporation.get_object(alliance_data["executor_corporation_id"])

    alliance.save()

    CcpIdTypeResolver.add_type(alliance_id,"alliance")
    return alliance

