# we need to keep these model-specific tasks in the model file
# trust me it's just cleaner that way when maintaining the code.
import logging
from eve_api.models.object_type import import_item_type, import_all_item_types
from eve_api.models.region import import_universe_region
from eve_api.models.constellation import import_universe_constellation
from eve_api.models.system import import_universe_system
from eve_api.tasks import provision_esi_character, provision_esi_corporation
from eve_api.models import EVEPlayerCorporation, EVEPlayerCharacter
from eve_api.esi_client import EsiClient
from eve_api.models import EVEPlayerAlliance, EVEPlayerCharacter, CcpIdTypeResolver
from eve_api.tasks import update_character_affiliations
from .util import is_downtime
from django.db.models import Q
from random import randint


logger = logging.getLogger(__name__)


def update_corp_member_info(corporation_id):
        d_chars = EVEPlayerCharacter.objects.filter(corporation__id=corporation_id, esi_key_may_grant_services=True, roles__name="roleDirector", _esi_roles__esi_corporations_read_corporation_membership_v1=True).all()
        if not d_chars:
            logger.warning("no available character for membership checking %s" % corporation_id)
            return
        d_char = d_chars.all()[randint(0, d_chars.count() - 1)]
        if not d_char.has_esi_scope('esi-corporations.read_corporation_membership.v1'):
            logger.warning("%s [%s] does not have scopes to read membership" % (d_char, d_char.corporation.name))
            return
        if d_char:
            client = EsiClient(authenticating_character=d_char)
            res, _ = client.get("/v3/corporations/%s/members/" % d_char.corporation.pk)
            if res:
                corpmembers = EVEPlayerCharacter.objects.filter(pk__in=res).all()
                currentmembers = [c.pk for c in corpmembers]
                provision_esi_corporation(corp_id=d_char.corporation.pk, force=True)
                missing = list(set(res) - set(currentmembers))
                if missing:
                    for misc in missing:
                        provision_esi_character(misc)
                update_character_affiliations(currentmembers)


def enqueue_corp_membership_updates():
    if is_downtime():
        return
    for trackedcorp in EVEPlayerCorporation.objects.filter((Q(alliance__track_membership=True) | Q(track_membership=True))).iterator():
        update_corp_member_info.delay(trackedcorp.pk)
