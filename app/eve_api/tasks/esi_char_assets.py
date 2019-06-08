import logging

from django.db.models import Q

from eve_api.esi_client import EsiClient, EsiError
from eve_api.models import EVEPlayerCharacter, Structure, Location, System, ObjectType, EsiKey
logger = logging.getLogger(__name__)


def update_asset_names(character, assets, container_names_only = True):
    """

    :param character:
    :param assets:
    :return:
    """
    item_ids = []
    for item in assets:
        # these conditionals are hacks to skip asset naming for asset categories known to cause issues with the
        # /character/assets/names endpoint. it's not perfect.
        if not item["is_singleton"]:
            continue
        if not (
            item["location_flag"] == "Deliveries" or
            item["location_flag"] == "Hangar" or
            item["location_flag"] == "FleetHangar" or
            item["location_flag"] == "AssetSafety" or
            item["location_flag"] == "ShipHangar"
        ):
            continue
        if container_names_only:
            if item["is_in_container"]:
                continue
            if not item["type"].market_group:
                continue
            if item["type"].market_group.parent_id != 379:
                continue

        item_ids.append(item["item_id"])

    pages = int(len(item_ids)/ 1000) + 1
    if len(item_ids) % 1000 == 0:
        pages -= 1

    cur_page = 0

    asset_names = []

    client = EsiClient(authenticating_character=character, log_application_errors=False, raise_application_errors=False)
    while cur_page < pages:
        subset = item_ids[cur_page * 1000: (cur_page+1)*1000]
        names, err = client.post("/v1/characters/%s/assets/names/" % (character.pk), post_body=subset)
        if err == EsiError.EsiApplicationError:
            logger.error("Character %s has assets that are crapping out the names endpoint. total items: %s" % (character.pk, len(item_ids)))
            cur_page += 1
            continue

        asset_names += names
        cur_page += 1

    asset_names_dict = {}
    for asset in asset_names:
        asset_names_dict[asset["item_id"]] = asset

    for asset in assets:
        if asset["item_id"] in asset_names_dict:
            asset["name"] = asset_names_dict[asset["item_id"]]["name"]
    return assets


def resolve_location_tree(
        root_location_id,
        root_location,
        base_asset,
        asset_list,
        location_id_hashtable,
        parent_container=None
    ):
    if not Location.exists(base_asset["item_id"]):
        location, _ = Location.objects.get_or_create(
            ccp_id=base_asset["item_id"],
            defaults={
                "parent_container": parent_container,
                "system": root_location.system,
                "constellation": root_location.constellation,
                "region": root_location.region,
                "root_location_id": root_location_id
            }
        )
        location.save()

    # we need to check if any children of the base_asset are containers themselves.
    for asset in asset_list:
        # is asset a direct child of base_asset?
        if asset["location_id"] == base_asset["item_id"]:
            # does asset have children?
            if asset["item_id"] in location_id_hashtable:
                resolve_location_tree(
                    root_location_id,
                    root_location,
                    asset,
                    asset_list,
                    location_id_hashtable,
                    base_asset["item_id"])



def sort_assets_into_structures(assets, item_id_hashtable, container_candidate_hashtable, character):
    """
    Returns a list of assets that sitting DIRECTLY inside a structure. Items in containers or ships are excluded.
    Returns an updated container_candidate_hashtable & item_id hashtable & assets list that excludes pocos,
    which tend to cause a shit ton of problems else where.
    :param assets:
    :param item_id_hashtable:
    :param container_candidate_hashtable:
    :param character:
    :return:
    """
    items_in_structures = []

    for asset in assets:
        if asset["location_id"] not in item_id_hashtable:
            items_in_structures.append(asset)
            # Handle side case when the "structure" an asset is inside is actually the character's pod
            if asset["location_id"] == character.pk:
                continue
            else:
                if asset["location_id"] > 60000000 and asset["location_id"] < 64000000:
                    # station
                    Structure.verify_object_exists(asset["location_id"], character.pk)
                elif asset["location_id"] > 30000000 and asset["location_id"] <= 32000000:
                    # it's a system id
                    Location.verify_object_exists(asset["location_id"], character.pk)
                else:
                    # it's either a structure or a poco
                    try:
                        Structure.verify_object_exists(asset["location_id"], character.pk)
                    except Exception as e:
                        # it's a poco and there's nothing we can do about it
                        del item_id_hashtable[asset["item_id"]]
                        try:
                            del container_candidate_hashtable[asset["location_id"]]
                        except KeyError:
                            pass
                        items_in_structures.remove(asset)
                        assets.remove(asset)
                        continue

    return items_in_structures, container_candidate_hashtable, item_id_hashtable, assets


def resolve_container_locations(assets, item_id_hashtable, items_in_structures, container_candidate_hashtable, character):
    """
    Resolves the Location of any containers in the assets
    :param assets:
    :param item_id_hashtable:
    :param items_in_structures:
    :param container_candidate_hashtable:
    :return:
    """
    for asset in items_in_structures:
        if asset["item_id"] in container_candidate_hashtable:
            # This asset has children. It needs a Location created for it.

            # we've got three possibilities at this point:
            # 1. The object is sitting inside a structure, and its root location is the structure
            # 2. The object is sitting inside another container, and its root location is that container
            # 3. The object is sitting in space, and its root location is that star system.

            # If the object is inside another container, then we still don't know if the whole shebang is in space,
            # inside a structure, or what. We only want to call resolve_location_tree for a single "tree" of containers,
            # so if this container isn't at the top of the stack, we skip it.

            if asset["location_id"] in item_id_hashtable:
                continue

            # need to figure out if root location is a Structure or a System
            if asset["location_id"] > 30000000 and asset["location_id"] <= 32000000:
                base_system = System.get_object(ccp_id=asset["location_id"])
                root_location_id = base_system.ccp_id
                root_location = Location.get_object(root_location_id, character.pk)
            else:
                if Structure.exists(ccp_id=asset["location_id"]):
                    base_structure = Structure.get_object(asset["location_id"], character.pk)
                    root_location_id = base_structure.ccp_id
                    root_location = base_structure.location

                else:
                    msg = "The asset is located in an unknown entity type, unable to resolve root location. Asset Location ID: %s Asset Item ID: %s, Character Trigger: %s" % (asset["location_id"], asset["item_id"], character.pk)
                    logger.critical(msg)
                    raise Exception(msg)

            resolve_location_tree(root_location_id, root_location, asset, assets, container_candidate_hashtable)


def extract_assets(character, assets):
    # before we do ANYTHING, make sure the character has a location that points at itself.
    location, _ = Location.objects.get_or_create(ccp_id=character.pk, defaults={"root_location_id": character.pk})
    location.save()

    # remove assets with an item_id over 9000000000000000000. they are bugged items. -ccp cockroach
    for item in assets:
        if item["item_id"] > 9000000000000000000:
            assets.remove(item)

    # create new assets
    # first we need to figure out what items are in containers, and which items are in structures

    # hash table of all item_ids in the asset list with a value of their location
    item_id_hashtable = {}

    # hash table of every location id in the asset list
    container_candidate_hashtable = {}

    for asset in assets:
        item_id_hashtable[asset["item_id"]] = asset["location_id"]
        container_candidate_hashtable[asset["location_id"]] = True

    items_in_structures, container_candidate_hashtable, item_id_hashtable, assets = sort_assets_into_structures(
        assets,
        item_id_hashtable,
        container_candidate_hashtable,
        character
    )

    resolve_container_locations(
        assets,
        item_id_hashtable,
        items_in_structures,
        container_candidate_hashtable,
        character
    )

    asset_objects = []
    for asset in assets:
        is_in_container = asset["location_id"] in item_id_hashtable
        if not Location.exists(asset["location_id"]):
            # todo: if this triggers, the item is most likely trashed. either remove item from assets or flag it explicitly
            logger.warning("Asset location could not be found. char: %s asset_info: %s in_container: %s" % (character.pk, asset, is_in_container))
            continue
        location = Location.get_object(asset["location_id"], character.pk)

        # resolve type
        item_type = ObjectType.get_object(asset["type_id"])

        asset_obj = {
            "location_flag": asset["location_flag"],
            "location": location,
            "is_in_container": is_in_container,
            "is_blueprint_copy": asset.get("is_blueprint_copy"),
            "is_singleton": asset["is_singleton"],
            "item_id": asset["item_id"],
            "location_type": asset["location_type"],
            "quantity": asset["quantity"],
            "type": item_type,
            "name": None
        }
        asset_objects.append(asset_obj)

    return update_asset_names(character, asset_objects)


def get_character_assets(character_ccp_id):
    """

    :param character_ccp_id:
    :return:
    {
    location_flag : varchar
    location : ORM Location
    is_in_container : bool
    is_blueprint_copy: nullable bool
    is_singleton: bool
    item_id: bigint
    location_type: varchar
    quantity: bigint
    type: ORM ObjectType

    }
    """
    character = EVEPlayerCharacter.get_object(character_ccp_id)

    # just assume they have the fuckin scope
    #char_keys = EsiKey.objects.filter(
    #    Q(character_id = character_ccp_id) &
    #    Q(use_key=True)
    #)

    #for key in char_keys:
    #    if key.has_esi_scope('esi-assets.read_assets.v1'):

    #if not character.has_esi_scope():
    #    return None

    client = EsiClient(authenticating_character=character)
    assets_pages = client.get_multiple_paginated("/v3/characters/{}/assets/".format(character_ccp_id))
    assets = extract_assets(character, assets_pages)
    return assets






