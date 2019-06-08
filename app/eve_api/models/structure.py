from django.db import models
import logging, requests
from .location import Location
from eve_api.esi_client import EsiClient
from django.db.utils import InternalError, IntegrityError
from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction

logger = logging.getLogger(__name__)


class Structure(models.Model):
    ccp_id = models.BigIntegerField(primary_key=True)

    name = models.CharField(max_length=255, default=None, null=True)
    type = models.ForeignKey("ObjectType", default=None, null=True, on_delete=models.CASCADE)
    is_blank = models.BooleanField(default=False)
    location = models.ForeignKey("Location", default=None, on_delete=models.CASCADE)

    market_last_updated = models.DateTimeField(default=None, null=True)
    market_data_expires = models.DateTimeField(default=None, null=True)

    class Meta:
        select_on_save = True

    def __unicode__(self):
        if self.name:
            return self.name
        else:
            return u"(%d)" % self.id

    def __str__(self):
        return self.__unicode__()

    @staticmethod
    def import_object(ccp_id, origin_character_id):
        try:
            import_structure(structure_id=ccp_id, origin_character_id=origin_character_id)
        except IntegrityError:
            pass

    @staticmethod
    def verify_object_exists(ccp_id, origin_character_id):
        # check cache
        exists = cache.get("structure_exists_%s" % (ccp_id))
        if exists:
            return

        # check db
        exists = Structure.exists(ccp_id)
        if not exists:
            Structure.import_object(ccp_id=ccp_id, origin_character_id=origin_character_id)

        # add to cache
        cache.set("structure_exists_%s" % (ccp_id), True, timeout=None)
        return


    @staticmethod
    def exists(ccp_id):
        """
        Cache-backed exists method. Cache only hits for Structures we know exist.
        :param ccp_id:
        :return:
        """
        exists = cache.get("structure_exists_%s" % ccp_id)
        if exists is not None:
            return True
        else:
            exists_db = Structure.objects.filter(pk=ccp_id).exists()
            if exists_db:
                cache.set("structure_exists_%s" % ccp_id, True, timeout=None)
            return exists_db

    @staticmethod
    def get_cached_name(ccp_id):
        """
        Gets a structure's current name from cache.
        :param ccp_id:
        :return:
        """
        name = cache.get('structure_name_{}'.format(ccp_id))
        if name:
            return name
        # guess we gotta load it
        s = Structure.get_object(ccp_id, None)

        cache.set('structure_name_{}'.format(ccp_id), s.name, timeout=None)
        return s.name


    @staticmethod
    def get_object(ccp_id, origin_character_id):
        cached_obj = cache.get("cached_eve_structure:%s" % ccp_id)
        if cached_obj is not None:
            return cached_obj
        else:
            try:
                item = Structure.objects.get(ccp_id=ccp_id)
                if item.is_blank:

                    # we don't have any info about this structure.
                    # consider using this char's auth to load the structure.

                    # if no character provided, just return the stub structure
                    if origin_character_id is None:
                        pass
                    has_tried_to_load_struct = cache.get("tried_to_load_%s_%s" % (ccp_id, origin_character_id))
                    if has_tried_to_load_struct:
                        # we've tried loading this structure before using this character's auth and it didn't work.
                        pass
                    else:
                        # let's try to load the structure
                        cache.set("tried_to_load_%s_%s" % (ccp_id, origin_character_id), "hello", timeout=3600)
                        Structure.import_object(ccp_id, origin_character_id)
                        new_item = Structure.objects.get(ccp_id=ccp_id)
                        if not new_item.is_blank:
                            logger.warning("successfully filled out structure data")
                        item =  new_item
                # we only cache structures that are not blank
                if not item.is_blank:
                    cache.set("cached_eve_structure:%s" % ccp_id, item, timeout=None)
                return item

            except Exception as e:
                if origin_character_id is None:
                    return None
                Structure.verify_object_exists(ccp_id, origin_character_id)
                return Structure.objects.get(ccp_id=ccp_id)


    @staticmethod
    def load_citadels_async(structure_ids, esi_client):
        if not structure_ids:
            return

        completely_new_structures = []
        structures_need_name_refresh = []
        structures_to_ignore = []
        for structure_id in structure_ids:
            if not Structure.exists(structure_id):
                completely_new_structures.append(structure_id)
            elif "Unknown Structure #" in Structure.get_cached_name(structure_id):
                structures_need_name_refresh.append(structure_id)
            else:
                structures_to_ignore.append(structure_id)

        structures_to_query = completely_new_structures + structures_need_name_refresh
        logger.info("Performing async citadels load for {} structures".format(len(structures_to_query)))
        endpoint = "/v2/universe/structures/{}/"
        results = esi_client.get_multiple(endpoint, structures_to_query)
        logger.info("Async citadel load completed")

        for ccp_id, data in results.items():
            import_citadel_from_data(data, ccp_id)

    @staticmethod
    def load_stations_async(station_ids, esi_client):
        if not station_ids:
            return
        logger.info("Performing async stations load for {} structures".format(len(station_ids)))
        endpoint = "/v2/universe/stations/{}/"
        results = esi_client.get_multiple(endpoint, station_ids)
        logger.info("Async station load completed")

        for ccp_id, data in results.items():
            if not Structure.exists(ccp_id):
                import_station_from_data(data, ccp_id)


@receiver(post_save, sender=Structure)
def structure_name_invalidator(sender, instance, **kwargs):
    structure_id = instance.pk
    keys = [x.format(structure_id) for x in ['structure_name_{}', "cached_eve_structure:{}"]]
    cache.delete_many(keys)

    cache.set('structure_name_{}', instance.name, timeout=None)
    cache.set("cached_eve_structure:{}".format(instance.pk), instance, timeout=None)


from eve_api.models import EVEPlayerCharacter
from .system import System
from .object_type import ObjectType


def import_citadel(structure_id, character):
    """
    Imports the citadel with the given structure_id, using esi token of the provided character.
    If character doesn't have docking access to the citadel, structure is created with the name "Unknown Structure#<ccpid>"
    Note that every Structure object also has a corresponding "Location". If a citadel has to be imported as an unknown
    structure, the structure's Location will have jack shit information.
    :param structure_id:
    :param character:
    :return:
    """
    client = EsiClient(authenticating_character=character, log_application_errors=False, raise_application_errors=False)
    structure, err = client.get("/v2/universe/structures/%s/" % structure_id)
    import_citadel_from_data(structure, structure_id)


def import_citadel_from_data(structure, structure_id):
    if structure.get("error") == "Forbidden":
        # for whatever reason this character isn't on the structure's ACL. Create skeleton object.
        logger.info("character isnt on structure %s acl" % structure_id)
        l,loc_created = Location.objects.get_or_create(
            ccp_id=structure_id,
            defaults={"root_location_id": structure_id,}
        )
        if loc_created:
            l.save()

        s, struct_created = Structure.objects.get_or_create(
            ccp_id=structure_id,
            defaults = {
                "name":"Unknown Structure #%s" % structure_id,
                "type":None,
                "is_blank":True,
                "location" : l
                }
        )
        if struct_created:
            s.save()

    else:
        structure_type = ObjectType.get_object(structure["type_id"]) if structure.get("type_id") is not None else None
        system = System.get_object(structure["solar_system_id"])
        l,_ = Location.objects.update_or_create(
            ccp_id=structure_id,
            defaults={
                "system": system,
                "constellation": system.constellation,
                "region": system.constellation.region,
                "root_location_id": structure_id,
            }
        )
        l.save()

        s, _ = Structure.objects.update_or_create(
            ccp_id=structure_id,
            defaults = {
                "name":structure["name"],
                "type":structure_type,
                "is_blank":False,
                "location" : l
            }
        )
        s.save()


def import_station(structure_id):
    """
    Imports a station.
    :param structure_id:
    :return:
    """
    client = EsiClient()
    structure, _ = client.get("/v2/universe/stations/%s/" % structure_id)

    if "error" in structure:
        if structure["error"] == "Station not found":
            return None
    import_station_from_data(structure, structure_id)


@transaction.atomic
def import_station_from_data(structure, structure_id):
    structure_type = ObjectType.get_object(structure["type_id"])
    system = System.get_object(structure["system_id"])
    l,_ = Location.objects.get_or_create(
        ccp_id=structure_id,
        defaults={
        "system":system,
        "constellation":system.constellation,
        "region":system.constellation.region,
        "root_location_id": structure_id,
        }
    )
    l.save()

    s = Structure(
        name=structure["name"],
        type=structure_type,
        is_blank=False,
        ccp_id=structure_id,
        location=l
    )
    s.save()


def import_structure(structure_id, origin_character_id):
    """
    Imports a generic structure (citadels, stations, outposts).
    :param self:
    :param structure_id:
    :param origin_character_id: Character to use for authentication purposes. (citadels require authentication to import properly)
    :return:
    """
    character = EVEPlayerCharacter.objects.get(pk=origin_character_id)
    structure_id = int(structure_id)
    # we're going to probably eat shit for this some day.
    if structure_id < 60000000:
        raise Exception("that's not a valid structure id (i think lol)")
        #return ImportObjectResult.ObjectNotFoundInESI
    if structure_id > 1000000000000:
        import_citadel(structure_id = structure_id, character=character)
    else:
        import_station(structure_id = structure_id)
    return

