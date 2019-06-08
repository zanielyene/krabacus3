from eve_api.models import EVEPlayerCorporation, EVEPlayerCharacter, EVEPlayerAlliance, CcpIdTypeResolver
from eve_api.models import System
from django.utils import timezone
from eve_api.esi_client import EsiClient


def is_downtime():
    client = EsiClient(bypass_cache=True)
    res,_ = client.get("/v1/status/")
    return False if int(res["players"]) > 100 else True

def verify_generic_object_exists(object_type, ccp_object_id):
    """
    Used by wallet/evemail endpoints since they have fields that are generic object ids
    :param object_type:
    :param object_pk:
    :return:
    """
    if object_type == "character":
        EVEPlayerCharacter.verify_object_exists(ccp_object_id)
    elif object_type == "corporation":
        EVEPlayerCorporation.verify_object_exists(ccp_object_id)
    elif object_type == "alliance":
        EVEPlayerAlliance.verify_object_exists(ccp_object_id)
    elif object_type == "system":
        System.verify_object_exists(ccp_object_id)
    elif object_type == "mailing_list":
        CcpIdTypeResolver.add_type(ccp_object_id, "mailing_list")
        pass
    elif object_type == "eve_system":
        return
    elif object_type == "faction":
        CcpIdTypeResolver.add_type(ccp_object_id, "faction")
    else:
        raise Exception("not implemented %s id %s" % (object_type, ccp_object_id) )