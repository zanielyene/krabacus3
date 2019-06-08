from eve_api.models import *
import logging, requests
from eve_api.esi_client import EsiClient
from django.db.utils import InternalError, IntegrityError
from django.db import transaction
from conf.huey_queues import general_queue

logger=logging.getLogger(__name__)


def import_type_category(ccp_id):
    client = EsiClient()
    g,_ = client.get("/v1/universe/categories/%s/" % ccp_id)
    category = TypeCategory(
        ccp_id = ccp_id,
        name = g["name"],
    )
    category.save()


@general_queue.task()
def import_all_type_categories():
    client = EsiClient()
    category_ids, _ = client.get("/v1/universe/categories/")

    group_data = client.get_multiple("/v1/universe/categories/{}/", category_ids)

    logger.info("all category data downloaded")

    category_objects = []
    for data in group_data.values():
        m = TypeCategory(
            ccp_id = data["category_id"],
            name = data["name"]
        )
        category_objects.append(m)
    logger.info("category data objects created")
    TypeCategory.objects.bulk_create(category_objects)
    logger.info("category data objects committed")


class TypeCategory(models.Model):
    ccp_id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=128)

    class Meta:
        select_on_save = True

    def __str__(self):
        return self.name

    @staticmethod
    def import_object(ccp_id):
        try:
            import_type_category(ccp_id)
        except IntegrityError:
            pass

    @staticmethod
    def verify_object_exists(ccp_id):
        exists = TypeCategory.objects.filter(ccp_id=ccp_id).exists()
        if not exists:
            TypeCategory.import_object(ccp_id)

    @staticmethod
    def get_object(ccp_id):
        try:
            item = TypeCategory.objects.get(ccp_id=ccp_id)
            return item
        except Exception as e:
            TypeCategory.verify_object_exists(ccp_id)
            return TypeCategory.objects.get(ccp_id=ccp_id)