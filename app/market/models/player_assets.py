import logging
import hashlib
from django.db import models
from eve_api.models import Structure, EVEPlayerCharacter, ObjectType


logger=logging.getLogger(__name__)


class AssetContainer(models.Model):
    ccp_id = models.BigIntegerField(primary_key=True)
    character = models.ForeignKey(EVEPlayerCharacter, on_delete=models.CASCADE)
    structure = models.ForeignKey(Structure, on_delete=models.CASCADE)
    name = models.CharField(max_length=128, default=None, null=True)

    def __str__(self):
        return self.name


class AssetEntry(models.Model):
    ccp_id = models.BigIntegerField(primary_key=True)
    character = models.ForeignKey(EVEPlayerCharacter, on_delete=models.CASCADE)
    container = models.ForeignKey(AssetContainer,default=None, null=True, on_delete=models.CASCADE)
    structure = models.ForeignKey(Structure, on_delete=models.CASCADE)

    quantity = models.BigIntegerField()
    object_type = models.ForeignKey(ObjectType, on_delete=models.CASCADE)

    @staticmethod
    def generate_hash(character_id):
        assets_hashable = AssetEntry.objects.filter(character_id=character_id).order_by('ccp_id').values_list('ccp_id', 'object_type_id', 'quantity', 'structure_id', 'container_id')
        assets_list = [a for a in assets_hashable]
        # order by ccp_id
        assets_list = sorted(assets_list, key=lambda a: a[0])

        algo = hashlib.new('SHA256')
        algo.update(str(assets_list).encode('utf-8'))
        hash_hexstr = algo.hexdigest()
        return hash_hexstr

    @staticmethod
    def generate_has_from_list(assets):
        assets_hashtable = []
        for a in assets:
            assets_hashtable.append(
                    (
                        int(a["item_id"]),
                        int(a["type"].pk),
                        int(a["quantity"]),
                        int(a["location"].root_location_id),
                        None if not a["is_in_container"] else int(a["location"].pk)
                     )
                )

        # order by ccp_id
        assets_list = sorted(assets_hashtable, key=lambda a: a[0])
        algo = hashlib.new('SHA256')
        algo.update(str(assets_list).encode('utf-8'))
        hash_hexstr = algo.hexdigest()
        return hash_hexstr

