import logging, uuid
from django.contrib.auth.models import User
from django.db import models
from eve_api.models import Structure, EVEPlayerCharacter, ObjectType
from .market_order import MarketOrder

logger=logging.getLogger(__name__)


class ItemGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creator = models.ForeignKey(User, default=None, null=True, on_delete=models.CASCADE)

    name = models.CharField(max_length=190)
    items = models.ManyToManyField(ObjectType)


    def __str__(self):
        return self.name
