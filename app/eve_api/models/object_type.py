from eve_api.models import *
import logging
from eve_api.esi_client import EsiClient
from django.db.utils import InternalError, IntegrityError
from django.core.cache import cache
from django.db.models.signals import post_save
import time, logging
from conf.huey_queues import general_queue

logger=logging.getLogger(__name__)


class ObjectType(models.Model):
    ccp_id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    volume = models.BigIntegerField(default=None, null=True)
    packaged_volume = models.FloatField(default=None, null=True)
    group = models.ForeignKey(TypeGroup, default=None, null=True, on_delete=models.CASCADE)
    icon_id = models.BigIntegerField()
    market_group = models.ForeignKey(MarketGroup, default=None, null=True, on_delete=models.CASCADE)
    published = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    class Meta:
        select_on_save = True
        index_together = [
            ("market_group", "published"),
        ]

    @staticmethod
    def import_object(ccp_id):
        try:
            import_item_type(type_id=ccp_id)
        except IntegrityError:
            pass

    @staticmethod
    def verify_object_exists(ccp_id, force=False):
        cached_obj = cache.get("cache_object_type:%s" % ccp_id)
        if cached_obj is not None and not force:
            return
        else:
            exists = ObjectType.objects.filter(ccp_id=ccp_id).exists()
            if not exists or force:
                ObjectType.import_object(ccp_id)
            # load object so it's in cache
            _ = ObjectType.get_object(ccp_id)

    @staticmethod
    def get_object(ccp_id):
        cached_obj = cache.get("cache_object_type:%s" % ccp_id)
        if cached_obj is not None:
            return cached_obj
        else:
            try:
                item = ObjectType.objects.get(ccp_id=ccp_id)
            except Exception as e:
                ObjectType.verify_object_exists(ccp_id)
                item = ObjectType.objects.get(ccp_id=ccp_id)
            cache.set("cache_object_type:%s" % ccp_id, item, timeout=None)
        return item

    @staticmethod
    def get_cached_item_names_multi(ccp_ids):
        key = "cache_object_type_name_{}"
        keys = [key.format(i) for i in ccp_ids]

        res = cache.get_many(keys)

        ret = []
        keys_to_set = {}
        for obj_id, obj_key in zip(ccp_ids, keys):
            if obj_key in res:
                ret.append(res[obj_key])
            else:
                o = ObjectType.get_object(obj_id)
                ret.append(o.name)
                keys_to_set[obj_key] = o.name

        if keys_to_set:
            cache.set_many(keys_to_set, timeout=None)
        return ret

    @staticmethod
    def get_cached_item_volumes_multi(ccp_ids):
        key = "cache_object_volume_{}"
        keys = [key.format(i) for i in ccp_ids]

        res = cache.get_many(keys)

        ret = []
        keys_to_set = {}
        for obj_id, obj_key in zip(ccp_ids, keys):
            if obj_key in res:
                ret.append(res[obj_key])
            else:
                o = ObjectType.get_object(obj_id)
                ret.append(o.packaged_volume)
                keys_to_set[obj_key] = o.packaged_volume

        if keys_to_set:
            cache.set_many(keys_to_set, timeout=None)
        return ret

    @staticmethod
    def get_all_tradeable_items():
        return ObjectType.objects.filter(market_group__isnull=False, published=True).values_list('ccp_id', flat=True)


def import_item_type(type_id):
    """
    Imports object type with the given type id. Does not return until after db transaction is committed.
    Only updates if item is already imported.
    :param self:
    :param type_id:
    :return:
    """
    logger.info("import_item_type task start with typeid %s" % type_id)
    client = EsiClient(raise_application_errors=False, log_application_errors=False)
    item_data, _ = client.get("/v3/universe/types/%s/" % type_id)
    if _ is not None:
        logger.error("received error when querying universe/types for {} err: {}".format(type_id, _))
        return
    item, _ = ObjectType.objects.update_or_create(
        ccp_id = type_id,
        defaults={
            "name" : item_data["name"],
            "volume" : item_data.get("volume"),
            "packaged_volume" : item_data.get("packaged_volume"),
            "group" : TypeGroup.get_object(item_data.get("group_id")),
            "icon_id": item_data.get("icon_id") if item_data.get("icon_id") else type_id,
            "market_group": MarketGroup.get_object(item_data.get("market_group_id")),
            "published": item_data["published"]
        }

    )
    item.save()
    return


@general_queue.task()
def import_all_item_types():
    """
    Imports all eve item types. This should only be called once when the database is initially set up.
    :param self:
    :return:
    """
    client = EsiClient()
    page_count = client.get_page_count("/v1/universe/types/")

    logger.info("{} pages of items to download".format(page_count))

    data = client.get_multiple("/v1/universe/types/?page={}", [p+1 for p in range(page_count)])

    logger.info("all pages downloaded")

    item_ids = []
    for page_data in data.values():
        item_ids.extend(page_data)

    item_data = client.get_multiple("/v3/universe/types/{}/", item_ids)
    logger.info("all item data downloaded")
    item_objs = []
    for item in item_data.values():
        i = ObjectType.objects.update_or_create(
            ccp_id = item["type_id"],
            defaults= {
            "name" :item["name"],
            "volume" : item.get("volume"),
            "packaged_volume" : item.get("packaged_volume"),
            "group_id" : item["group_id"],
            "icon_id" : item.get("icon_id") if item.get("icon_id") else item["type_id"],
            "market_group" : MarketGroup.get_object(item.get("market_group_id")),
            "published":item["published"]
        }
        )
        #i.save()
        item_objs.append(i)


    logger.info("all item data has objects created")
    ObjectType.objects.bulk_create(item_objs)
    logger.info("all item data committed")


@receiver(post_save, sender=ObjectType)
def objecttype_cache_invalidator(sender, instance, **kwargs):
    ccp_id = instance.pk
    keys = [x.format(ccp_id) for x in ['cache_object_volume_{}', 'cache_object_type_name_{}', 'cache_object_type:{}']]
    cache.delete_many(keys)
