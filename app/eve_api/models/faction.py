from django.db import models
import logging,requests
from eve_api.esi_client import EsiClient
from django.db.utils import InternalError, IntegrityError
from conf.huey_queues import general_queue

logger=logging.getLogger(__name__)


class Faction(models.Model):
    ccp_id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    is_unique = models.BooleanField()
    size_factor = models.FloatField()

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
            # we cant import a specific faction, must import them all
            import_universe_factions()

        except IntegrityError:
            pass

    @staticmethod
    def verify_object_exists(ccp_id):
        exists = Faction.objects.filter(ccp_id=ccp_id).exists()
        if not exists:
            Faction.import_object(ccp_id)

    @staticmethod
    def get_object(ccp_id):
        try:
            item = Faction.objects.get(ccp_id=ccp_id)
            return item
        except Exception as e:
            Faction.verify_object_exists(ccp_id)
            return Faction.objects.get(ccp_id=ccp_id)


@general_queue.task()
def import_universe_factions():
    """
    Imports all EVE Factions
    :return:
    """
    client = EsiClient()
    factions, _ = client.get("/v2/universe/factions/")

    for faction in factions:
        if Faction.objects.filter(ccp_id=faction["faction_id"]).exists():
            continue
        else:
            f = Faction(
                ccp_id = faction["faction_id"],
                name = faction["name"],
                is_unique = faction["is_unique"],
                size_factor = float(faction["size_factor"]),
            )
            f.save()

