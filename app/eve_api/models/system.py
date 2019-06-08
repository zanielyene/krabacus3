from django.db import models
import logging, requests
from eve_api.esi_client import EsiClient
from django.db.utils import InternalError, IntegrityError
from django.core.cache import cache
from conf.huey_queues import general_queue

logger = logging.getLogger(__name__)


# if anyone ever changes this to SolarSystem i'll fucking kill them
class System(models.Model):
    ccp_id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    constellation = models.ForeignKey("Constellation" , on_delete=models.CASCADE)
    security_status = models.FloatField()

    class Meta:
        select_on_save = True

    @property
    def printable_name(self):
        return self.name

    def __str__(self):
        return self.name

    @staticmethod
    def import_object(ccp_id):
        try:
            import_universe_system(system_id=ccp_id)
        except IntegrityError:
            pass

    @staticmethod
    def verify_object_exists(ccp_id):
        cached_obj = cache.get("cache_eve_system:%s" % ccp_id)
        if cached_obj is not None:
            return
        else:
            exists = System.objects.filter(ccp_id=ccp_id).exists()
            if not exists:
                System.import_object(ccp_id)
                # load object so it's in cache
                _ = System.get_object(ccp_id)

    @staticmethod
    def get_object(ccp_id):
        cached_obj = cache.get("cache_eve_system:%s" % ccp_id)
        if cached_obj is not None:
            return cached_obj
        else:
            try:
                item = System.objects.get(ccp_id=ccp_id)
            except Exception as e:
                import_universe_system(system_id=ccp_id)
                item = System.objects.get(ccp_id=ccp_id)
            cache.set("cache_eve_system:%s" % ccp_id, item, timeout=None)
            return item

    def region(self):
        return self.constellation.region


from .region import Region
from .constellation import Constellation
from .location import Location

@general_queue.task()
def import_universe_systems():
    client = EsiClient()
    systems, _ = client.get("/v1/universe/systems/")
    logger.info("dispatching system fetches")

    system_data = client.get_multiple("/v4/universe/systems/{}/", systems)
    system_objs = []
    for r in system_data.values():
        system_objs.append(
            System(
                ccp_id = r["system_id"],
                constellation_id = r["constellation_id"],
                name = r["name"],
                security_status = r["security_status"]
            )
        )
    System.objects.bulk_create(system_objs)
    logger.info("systems created & committed")

    # gen location data
    location_objs = []
    for system in System.objects.all():
        location_objs.append(
            Location(
                ccp_id = system.pk,
                system = system,
                constellation = system.constellation,
                region = system.constellation.region,
                root_location_id = system.pk,
                is_in_space = True
            )
        )
    Location.objects.bulk_create(location_objs)
    logger.info("system locations created & committed")

def import_universe_system(system_id):
    """
    Imports the given system_id if it hasn't already been imported. Also creates the system's corresponding Location.
    :param self:
    :param system_id:
    :return:
    """
    client = EsiClient()
    system_data, _ = client.get("/v4/universe/systems/%s/" % system_id)
    if not System.objects.filter(ccp_id=system_id).exists():
        constellation = Constellation.get_object(system_data["constellation_id"])
        system, _ = System.objects.get_or_create(
            ccp_id=system_id,
            defaults = {
                "name":system_data["name"],
                "constellation":constellation,
                "security_status":system_data["security_status"],
            }
        )
        system.save()

        # also create a Location for the system. This is utilized by assets in space
        location, _ = Location.objects.get_or_create(
            ccp_id = system_id,
            defaults = {
                "system":system,
                "constellation":constellation,
                "region":constellation.region,
                "root_location_id": system_id,
                "is_in_space": True
            }
        )
        location.save()
        from eve_api.models import CcpIdTypeResolver
        CcpIdTypeResolver.add_type(system_id, "system")
    return