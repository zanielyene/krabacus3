from django.db import models
import logging
from django.core.cache import cache

from eve_api.esi_client import EsiClient

logger = logging.getLogger(__name__)


class Location(models.Model):
    ccp_id = models.BigIntegerField(primary_key=True)
    parent_container = models.BigIntegerField(null=True, default=None)
    system = models.ForeignKey("System", null=True, default=None, on_delete=models.CASCADE)
    constellation = models.ForeignKey("Constellation", null=True, default=None, on_delete=models.CASCADE)
    region = models.ForeignKey("Region", null=True, default=None, db_index=True, on_delete=models.CASCADE)
    root_location_id = models.BigIntegerField(default=None, db_index=True)
    is_in_space = models.BooleanField(default=False)

    @staticmethod
    def import_object(ccp_id, origin_character_id):
        from .structure import Structure
        Structure.import_object(ccp_id=ccp_id, origin_character_id=origin_character_id)

    @staticmethod
    def verify_object_exists(ccp_id, origin_character_id):
        exists = Location.objects.filter(ccp_id=ccp_id).exists()
        if not exists:
            from .structure import Structure
            from .system import System
            # static universe objects are int32, dont hit the names endpoint if it's bigger
            if ccp_id <= 2147483647:
                client = EsiClient(log_application_errors=False, raise_application_errors=False)
                object_type, _ = client.post("/v2/universe/names/", post_body="[%s]" % ccp_id)
                if object_type.get("error") == "Ensure all IDs are valid before resolving.":
                    # no problemo, the id must map to a structure.
                    pass
                elif "error" not in object_type:
                    if object_type[0]["category"] == "solar_system":
                        System.import_object(ccp_id=ccp_id)
                    return
                else:
                    raise Exception("Unhandlable application error from /v2/universe/names/: %s ccp_id: %s" % (object_type, ccp_id))
            Structure.import_object(ccp_id=ccp_id, origin_character_id=origin_character_id)

    @staticmethod
    def exists(ccp_id):
        """
        Cache-backed exists method. Cache only hits for Locations we know exist.
        :param ccp_id:
        :return:
        """
        exists = cache.get("location_exists_%s" % ccp_id)
        if exists is not None:
            return True
        else:
            exists_db = Location.objects.filter(pk=ccp_id).exists()
            if exists_db:
                cache.set("location_exists_%s" % ccp_id, True, timeout=3600)
            return exists_db


    @staticmethod
    def get_object(ccp_id, origin_character_id):
        cached_obj = cache.get("cache_eve_location:%s" % ccp_id)
        if cached_obj is not None:
            return cached_obj
        else:

            try:
                item = Location.objects.get(ccp_id=ccp_id)
            except Exception as e:
                if origin_character_id is None:
                    return None
                Location.verify_object_exists(ccp_id, origin_character_id)
                item = Location.objects.get(ccp_id=ccp_id)
            cache.set("cache_eve_location:%s" % ccp_id, item, timeout=86400)
            return item

    class Meta:
        select_on_save = True