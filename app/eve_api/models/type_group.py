from eve_api.models import *
import logging, requests
from eve_api.esi_client import EsiClient
from django.db.utils import InternalError, IntegrityError
from django.db import transaction
from conf.huey_queues import general_queue

logger=logging.getLogger(__name__)


def import_type_group(ccp_id):
    client = EsiClient()
    g,_ = client.get("/v1/universe/groups/%s/" % ccp_id)
    group = TypeGroup(
        ccp_id = ccp_id,
        name = g["name"],
        category_id = g["category_id"]
    )
    group.save()


@general_queue.task()
def import_all_type_groups():
    client = EsiClient()
    # very lazy will regret
    group_ids, _ = client.get("/v1/universe/groups/?page=1")
    group_ids2, _ = client.get("/v1/universe/groups/?page=2")
    group_ids.extend(group_ids2)

    group_data = client.get_multiple("/v1/universe/groups/{}/", group_ids)

    logger.info("all group data downloaded")

    group_objects = []
    for data in group_data.values():
        m = TypeGroup(
            ccp_id = data["group_id"],
            name = data["name"],
            category_id = data["category_id"]
        )
        group_objects.append(m)
    logger.info("group data objects created")
    TypeGroup.objects.bulk_create(group_objects)
    logger.info("group data objects committed")


class TypeGroup(models.Model):
    ccp_id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    category = models.ForeignKey(TypeCategory, on_delete=models.CASCADE)

    class Meta:
        select_on_save = True

    def __str__(self):
        return self.name

    @staticmethod
    def import_object(ccp_id):
        try:
            import_type_group(ccp_id)
        except IntegrityError:
            pass

    @staticmethod
    def verify_object_exists(ccp_id):
        exists = TypeGroup.objects.filter(ccp_id=ccp_id).exists()
        if not exists:
            TypeGroup.import_object(ccp_id)

    @staticmethod
    def get_object(ccp_id):
        try:
            item = TypeGroup.objects.get(ccp_id=ccp_id)
            return item
        except Exception as e:
            TypeGroup.verify_object_exists(ccp_id)
            return TypeGroup.objects.get(ccp_id=ccp_id)