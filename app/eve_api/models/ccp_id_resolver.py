from django.db import models
import logging,requests
from eve_api.esi_client import EsiClient
from django.db.utils import InternalError, IntegrityError
from django.core.cache import cache
from eve_api.esi_client import EsiClient

logger = logging.getLogger(__name__)

CCP_ID_TYPE_GROUPS = (
    ('character', 'character'),
    ('corporation', 'corporation'),
    ('alliance', 'alliance'),
    ('system','star system'),
    ('faction','faction'),
    ('mailing_list','mailing list'),
)


class CcpIdTypeResolver(models.Model):
    ccp_id = models.BigIntegerField(primary_key=True)
    type_name = models.CharField(max_length=250, choices=CCP_ID_TYPE_GROUPS, null=True)

    @property
    def printable_name(self):
        return self.type_name

    def __str__(self):
        return self.type_name

    class Meta:
        select_on_save = True

    @staticmethod
    def resolve_type(ccp_id):
        client = EsiClient(log_application_errors=False, raise_application_errors=False)
        _, err = client.get("/v4/characters/%s/" % ccp_id)
        if err is None:
            return "character"
        _, err = client.get("/v4/corporations/%s/" % ccp_id)
        if err is None:
            return "corporation"
        _, err = client.get("/v3/alliances/%s/" % ccp_id)
        if err is None:
            return "alliance"
        return None

    @staticmethod
    def get_id_type(ccp_id):
        if ccp_id == 2:
            return "eve_system"
        if ccp_id <= 17:
            return None
        # https://gist.github.com/a-tal/5ff5199fdbeb745b77cb633b7f4400bb
        if 500000 <= ccp_id <= 1000000:
            return "faction"
        if 1000001 <= ccp_id <= 2000000:
            return "corporation"
        if 3000001 <= ccp_id <= 4000000:
            return "character"
        if 90000001 <= ccp_id <= 98000000:
            return "character"
        if 98000001 <= ccp_id <= 99000000:
            return "corporation"
        if 99000001 <= ccp_id <= 100000000:
            return "alliance"
        if 30000001 <= ccp_id <= 31000000:
            return "system"
        if 31000001 <= ccp_id <= 32000000:
            return "system"

        if 100000000 <= ccp_id <=  2147483647:
            # legacy organization (pre-2011)

            # check cache
            type_name = cache.get("ccp_id_type_name_resolver_%s" % ccp_id)
            if type_name is not None:
                return type_name

            if CcpIdTypeResolver.objects.filter(pk=ccp_id).exists():
                n = CcpIdTypeResolver.objects.get(pk=ccp_id).type_name
                if n:
                    # set cache
                    cache.set("ccp_id_type_name_resolver_%s" % ccp_id, n, timeout=604800)
                    return n
            type_name = CcpIdTypeResolver.resolve_type(ccp_id)
            type_obj, _ = CcpIdTypeResolver.objects.update_or_create(ccp_id=ccp_id, defaults={"type_name":type_name})
            type_obj.save()

            # set cache
            cache.set("ccp_id_type_name_resolver_%s" % ccp_id, type_name, timeout=604800)
            return type_name
        return None

    @staticmethod
    def add_type(ccp_id, type_name):
        # check to see if this type is in the static "already known" type_id keyspace.
        # if it's in the static keyspace, don't bother adding the type.
        # https://gist.github.com/a-tal/5ff5199fdbeb745b77cb633b7f4400bb
        if 500000 <= ccp_id <= 1000000:
            return
        if 1000001 <= ccp_id <= 2000000:
            return
        if 3000001 <= ccp_id <= 4000000:
            return
        if 90000001 <= ccp_id <= 98000000:
            return
        if 98000001 <= ccp_id <= 99000000:
            return
        if 99000001 <= ccp_id <= 100000000:
            return
        if 30000001 <= ccp_id <= 31000000:
            return
        if 31000001 <= ccp_id <= 32000000:
            return

        # check cache to see if we've already added this type
        already_added = cache.get("ccp_id_type_already_exists_%s" % ccp_id)
        if already_added is not None:
            return

        if not CcpIdTypeResolver.objects.filter(ccp_id=ccp_id).exists():
            t = CcpIdTypeResolver(ccp_id=ccp_id, type_name=type_name)
            t.save()

        cache.set("ccp_id_type_already_exists_%s" % ccp_id, True, timeout=604800)
