from eve_api.models import *
import logging, requests
from eve_api.esi_client import EsiClient
from django.db.utils import InternalError, IntegrityError
from django.db import transaction
from conf.huey_queues import general_queue

logger=logging.getLogger(__name__)


def import_market_group(ccp_id):
    client = EsiClient()
    g,_ = client.get("/v1/markets/groups/%s/" % ccp_id)
    group = MarketGroup(
        ccp_id = ccp_id,
        name = g["name"],
        parent_id = g.get("parent_group_id"),
    )
    group.save()


@general_queue.task()
def import_all_market_groups():
    client = EsiClient()
    group_ids, _ = client.get("/v1/markets/groups/")

    group_data = client.get_multiple("/v1/markets/groups/{}/", group_ids)

    logger.info("all group data downloaded")

    group_objects = []
    for data in group_data.values():
        # notice that this directly references category_id object, we expect categories to already be imported.
        m = MarketGroup(
            ccp_id = data["market_group_id"],
            parent_id = data.get("parent_group_id"),
            name = data["name"]
        )
        group_objects.append(m)
    logger.info("group data objects created")
    MarketGroup.objects.bulk_create(group_objects)
    logger.info("group data objects committed")

class MarketGroup(models.Model):
    ccp_id = models.BigIntegerField(primary_key=True)
    parent_id = models.BigIntegerField(default=None, null=True)
    name = models.CharField(max_length=128)

    class Meta:
        select_on_save = True

    def __str__(self):
        return self.name

    @staticmethod
    def import_object(ccp_id):
        try:
            import_market_group(ccp_id)
        except IntegrityError:
            pass

    @staticmethod
    def verify_object_exists(ccp_id):
        exists = MarketGroup.objects.filter(ccp_id=ccp_id).exists()
        if not exists:
            MarketGroup.import_object(ccp_id)

    @staticmethod
    def get_object(ccp_id):
        if ccp_id is None:
            return None
        try:
            item = MarketGroup.objects.get(ccp_id=ccp_id)
            return item
        except Exception as e:
            MarketGroup.verify_object_exists(ccp_id)
            return MarketGroup.objects.get(ccp_id=ccp_id)