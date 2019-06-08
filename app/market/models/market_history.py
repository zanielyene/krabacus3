import logging
import hashlib
from django.contrib.auth.models import User
import asyncio

from django.db import models
from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

from eve_api.models import Structure, EVEPlayerCharacter, ObjectType, Region
from market.utils import get_cached_column, obj_exists_cached
from conf.huey_queues import general_queue


logger = logging.getLogger(__name__)


class MarketHistory(models.Model):
    id = models.BigAutoField(primary_key=True, editable=False)
    object_type = models.ForeignKey(ObjectType, on_delete=models.CASCADE)
    date = models.DateField()

    average = models.FloatField()
    highest = models.FloatField()
    lowest = models.FloatField()
    order_count = models.BigIntegerField()
    volume = models.BigIntegerField()

    region = models.ForeignKey(Region, on_delete=models.CASCADE)

    class Meta:
        index_together = [
            ("region", "date", "object_type"),
        ]

    @staticmethod
    def get_market_history_cache_timeout():
        # 30 days
        return 30 * 86400

    @staticmethod
    def exists(object_id, region_id, date):
        cache_key = "market_history_exists_{}_{}_{}_{}_{}"
        k = cache_key.format(object_id, region_id, date.month, date.day, date.year)
        does_exist = cache.get(k)
        if does_exist:
            return True

        # check db
        exists = MarketHistory.objects.filter(
            region_id=region_id,
            date=date,
            object_type_id = object_id
        ).exists()
        if exists:
            cache.set(k, True, timeout=MarketHistory.get_market_history_cache_timeout())
        return exists



    @staticmethod
    def heat_cache():
        logger.info("Heating market history cache")
        all_entries = MarketHistory.objects.all()
        cache_key = "market_history_exists_{}_{}_{}_{}_{}"

        keys = {}
        for entry in all_entries:
            keys[
                cache_key.format(
                    entry.object_type_id,
                    entry.region_id,
                    entry.date.month,
                    entry.date.day,
                    entry.date.year
                )] = True

        cache.set_many(keys, timeout=MarketHistory.get_market_history_cache_timeout())
        logger.info("Market history cache hot with {} kv's".format(len(keys)))