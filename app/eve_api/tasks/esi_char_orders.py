import logging
import dateutil.parser

from eve_api.esi_client import EsiClient
from eve_api.models import EVEPlayerCharacter, ObjectType, Region, Structure

logger = logging.getLogger(__name__)


def extract_order(character, order):
    return {
        "duration": order["duration"],
        "escrow": float(order.get("escrow")) if order.get("escrow") is not None else None,
        "is_buy_order": False if order.get("is_buy_order") is None else order["is_buy_order"],
        "is_corporation": order["is_corporation"],
        "issued": dateutil.parser.parse(order["issued"]),
        "location": Structure.get_object(order["location_id"], character.pk),
        "min_volume":order.get("min_volume"),
        "order_id": int(order["order_id"]),
        "price": float(order["price"]),
        "range": order["range"],
        "type": ObjectType.get_object(order["type_id"]),
        "volume_remain":order["volume_remain"],
        "volume_total":order["volume_total"],
        "region":Region.get_object(order["region_id"])
    }


def get_character_orders(character_ccp_id):
    """
    :param character_ccp_id:
    :return:
     [
        {
            duration:int(total days order valid)
            escrow: float(nullable)
            is_buy_order: boolean (if CCP returns null for this, we assume sell order)
            is_corporation: boolean
            issued: datetime,
            location: Structure
            min_volume: int(nullable)
            order_id: int
            price: float
            range: string options([ 1, 10, 2, 20, 3, 30, 4, 40, 5, region, solarsystem, station ])
            type: object type
            volume_remain: int
            volume_total: int
            region: Region
        }
     ]
    """
    character = EVEPlayerCharacter.get_object(character_ccp_id)

    if not character.has_esi_scope('esi-markets.read_character_orders.v1'):
        return None

    client = EsiClient(authenticating_character=character)

    order_entries, _ = client.get("/v2/characters/%s/orders/" % character_ccp_id)

    ret = []
    for entry in order_entries:
        ret.append(extract_order(character, entry))
    return ret







