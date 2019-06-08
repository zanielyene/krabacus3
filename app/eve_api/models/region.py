from django.db import models
import logging,requests
from eve_api.esi_client import EsiClient
from django.db.utils import InternalError, IntegrityError
from conf.huey_queues import general_queue

logger=logging.getLogger(__name__)


class Region(models.Model):
    ccp_id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=255)

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
            import_universe_region(region_id=ccp_id)
        except IntegrityError:
            pass

    @staticmethod
    def verify_object_exists(ccp_id):
        exists = Region.objects.filter(ccp_id=ccp_id).exists()
        if not exists:
            Region.import_object(ccp_id)

    @staticmethod
    def get_object(ccp_id):
        try:
            item = Region.objects.get(ccp_id=ccp_id)
            return item
        except Exception as e:
            Region.verify_object_exists(ccp_id)
            return Region.objects.get(ccp_id=ccp_id)


@general_queue.task()
def import_universe_regions():
    client = EsiClient()
    regions, _ = client.get("/v1/universe/regions/")
    logger.info("dispatching region fetches")

    regions_data = client.get_multiple("/v1/universe/regions/{}/", regions)
    regions_objs = []
    for r in regions_data.values():
        regions_objs.append(
            Region(
                ccp_id = r["region_id"],
                name = r["name"]
            )
        )
    Region.objects.bulk_create(regions_objs)
    logger.info("regions created & committed")



def import_universe_region(region_id):
    """
    Imports the region with the given region_id, along with its constellations.
    Always imports region's constellations, even if region already existed.
    :param self:
    :param region_id:
    :return:
    """
    client = EsiClient()
    region_data, _ = client.get("/v1/universe/regions/%s/" % region_id)

    if not Region.objects.filter(ccp_id=region_id).exists():
        region_obj = Region(ccp_id=region_id, name=region_data["name"])
        region_obj.save()


    #group(
    #    import_universe_constellation.s(constellation)
    #
    #)()
    return

