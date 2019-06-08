import logging
from django.contrib.auth.models import User
import asyncio

from django.db import models
from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver
import uuid

from eve_api.models import Structure, EVEPlayerCharacter, ObjectType
from .trading_route import TradingRoute
logger=logging.getLogger(__name__)


class ShoppingListItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    route = models.ForeignKey(TradingRoute, on_delete=models.CASCADE)
    object_type = models.ForeignKey(ObjectType, on_delete=models.CASCADE)
    quantity = models.BigIntegerField()

    class Meta:
        index_together = [
            ['route', 'object_type']
        ]

    @staticmethod
    def get_route_shopping_lookup(route):
        items = ShoppingListItem.objects.filter(route=route)
        ret = {}
        for i in items:
            ret[i.object_type.pk] = i
        return ret


