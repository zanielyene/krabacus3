from django.db import models

import logging,requests
from eve_api.esi_client import EsiClient
from django.db.utils import InternalError, IntegrityError
from django.db import transaction
from conf.huey_queues import general_queue

logger = logging.getLogger(__name__)


class Constellation(models.Model):
    ccp_id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    region = models.ForeignKey("Region" , on_delete=models.CASCADE)

    @property
    def printable_name(self):
        return self.name

    def __str__(self):
        return self.name

    class Meta:
        select_on_save = True


    @staticmethod
    def import_object(ccp_id):
        try:
            import_universe_constellation(constellation_id=ccp_id)
        except IntegrityError:
            pass

    @staticmethod
    def verify_object_exists(ccp_id):
        exists = Constellation.objects.filter(ccp_id=ccp_id).exists()
        if not exists:
            Constellation.import_object(ccp_id)

    @staticmethod
    def get_object(ccp_id):
        try:
            item = Constellation.objects.get(ccp_id=ccp_id)
            return item
        except Exception as e:
            Constellation.verify_object_exists(ccp_id)
            return Constellation.objects.get(ccp_id=ccp_id)


from .system import import_universe_system
from .region import Region

@general_queue.task()
def import_universe_constellations():
    client = EsiClient()
    constellations, _ = client.get("/v1/universe/constellations/")
    logger.info("dispatching constellation fetches")

    constellations_data = client.get_multiple("/v1/universe/constellations/{}/", constellations)
    constellation_objs = []
    for r in constellations_data.values():
        constellation_objs.append(
            Constellation(
                ccp_id = r["constellation_id"],
                region_id = r["region_id"],
                name = r["name"]
            )
        )
    Constellation.objects.bulk_create(constellation_objs)
    logger.info("constellations created & committed")


def import_universe_constellation(constellation_id):
    """
    Imports the constellation with the given constellation id along with the constellation's systems.
    Attempts to import constellations systems even if constellation is already imported.
    :param self:
    :param constellation_id:
    :return:
    """
    client = EsiClient()
    constellation_data, _ = client.get("/v1/universe/constellations/%s/" % constellation_id)

    if not Constellation.objects.filter(ccp_id=constellation_id).exists():
        region = Region.get_object(constellation_data["region_id"])
        constellation_obj = Constellation(
            ccp_id=constellation_id,
            name=constellation_data["name"],
            region=region
        )
        constellation_obj.save()

    raise Exception("redo this group code")
    #group(
    #    import_universe_system.s(system)
    #    for system in constellation_data["systems"]
    #)()

    return