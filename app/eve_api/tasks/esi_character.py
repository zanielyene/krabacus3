import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.db.utils import InternalError
import sys
import pprint
import json
from datetime import datetime, timedelta
from django.utils import timezone
from django.utils.timezone import now
from requests_oauthlib import OAuth2Session

from eve_api import esi_exceptions, eve_oauth
from eve_api.esi_client import EsiClient, EsiError
from eve_api.models import *

import dateutil.parser

logger=logging.getLogger(__name__)

from eve_api.models import EVEPlayerCharacter, EVEPlayerCorporation
from django.conf import settings
import logging
from itertools import islice
from django.db.models import Q
from django.utils.timezone import now, utc
from .util import is_downtime

from .esi_char_walletbalance import get_character_balance

from eve_api.tasks.esi_corporation import set_corporation_affiliation, update_corporation_public_details

from raven import breadcrumbs


def soft_delete_esi_character_key(character_id):
    """
    Soft deletes an EvePlayerCharacter's ESI Key. This prevents the ESI key from granting services and being displayed
    to the character's owner. The key itself stays attached to the character as long as it is valid.
    If the character does not have a working ESI key, this task does not do anything.
    :param character_id:
    :return:
    """
    character = EVEPlayerCharacter.objects.get(id=character_id)
    if character.esi_key is None:
        return
    else:
        character.soft_delete_esi_key()
        return



def hard_delete_esi_character_key(character_id):
    """
    Hard deletes an EvePlayerCharacter's ESI key. This prevents the ESI key from granting services, and prevents
    future queries for character data using the key.
    If the character does not have a working ESI key, this task does not do anything.
    This task should only be used by sysadmins or auth management code. If you need to revoke keys for a non-weird reason,
    just call character.delete_revoked_esi_key yourself.
    :param char_id:
    :return:
    """
    character = EVEPlayerCharacter.objects.get(id=character_id)
    if character.esi_key is None:
        return
    else:
        character.delete_revoked_esi_key(commit_character_changes=True, revoked_by_sysadmin=True)
        return



def queue_esi_character_updates(batch_size=1000, update_interval_hours=24):
    if is_downtime():
        return

    logger = queue_esi_character_updates.get_logger()
    delta = timedelta(hours=update_interval_hours)

    # Get all characters for whom we have an ESI key where they have not been validated in the past 24 hours.
    out_of_date_characters = EVEPlayerCharacter.objects.filter(
        esi_key__isnull = False,
        esi_key_last_validated__isnull = False,
        esi_key_last_validated__lt = (now() - delta)
    )

    logger.info("Total of %d characters that need an ESI update", out_of_date_characters.count())

    # We only care about characters that haven't been queued for an update already
    #characters_to_update = []
    for idx, character in enumerate(out_of_date_characters):
        if idx < batch_size:
            try:
                update_eve_character_esi.delay(character.pk)
            except Exception as e:
                logger.error("Error raised while updating esi character: %s", e)
        else:
            return


def purge_doomheim_characters():
    if is_downtime():
        return

    doomheim_chars =  EVEPlayerCharacter.objects.filter(
        corporation__id = 1000001,
        owner__isnull=False
    )

    for char in doomheim_chars:
        if char.esi_key is not None:
            char.delete_revoked_esi_key()
        char.owner_hash = None
        char.owner = None
        char.save()
    return



def update_character_affiliations(character_list, chunk_size=990):
    if not character_list:
        return
    changed_corp_counter = 0
    client = EsiClient()
    # chunk into 990 sized lists
    for post_body in [character_list[x:x + chunk_size] for x in xrange(0, len(character_list), chunk_size)]:
        affiliations, _ = client.post("/v1/characters/affiliation/", post_body=post_body)
        if not affiliations:
            logger.exception("no affiliations returned from %s" % post_body)
            return
        for affiliation in affiliations:
            char = EVEPlayerCharacter.objects.get(pk=affiliation["character_id"])
            if "corporation_id" in affiliation:
                set_corporation_affiliation(affiliation["corporation_id"], affiliation.get("alliance_id"))

                if char.corporation.id != int(affiliation["corporation_id"]):
                    corp = EVEPlayerCorporation.get_object(affiliation["corporation_id"])
                    changed_corp_counter += 1
                    char.corporation = corp
                    char.save()
    logger.info("updated corporation of %s characters" % changed_corp_counter)
    # now update the publicdata_last_updated in bulk
    EVEPlayerCharacter.objects.filter(pk__in=character_list).update(publicdata_last_updated=timezone.now())


def bulk_update_character_affiliations(update_interval_hours=48):
    if is_downtime():
        return

    update_delay = timedelta(hours=update_interval_hours)
    day_ago = now() - update_delay

    # be sure to exclude npcs
    out_of_date_characters = EVEPlayerCharacter.objects.filter(
        (
            Q(publicdata_last_updated__isnull=True) |
            Q(publicdata_last_updated__lt=day_ago)
        ) &
        (
            (
                Q(id__gt=90000000) &
                Q(id__lte=98000000)
            ) |
            (
                Q(id__gt=100000000) &
                Q(id__lte=2147483648)
            )
        ) &
        Q(corporation__isnull=False) # characters without a corporation are either super old legacy characters or complete bugged out. legacy chars will get fixed the next time get_object is called on them.
    ).order_by("publicdata_last_updated")
    # only grab first thousand characters
    out_of_date_characters = out_of_date_characters[0:999]

    characters = [c.pk for c in out_of_date_characters]
    breadcrumbs.record("len(characters) = {}".format(len(characters)))
    if not characters:
        logger.info("no characters need updating. ending task")
        return
    update_character_affiliations(characters)


def esi_scopes_valid(scopes, required_scopes):
    # todo: implement allied scopes here
    # Verify that we received all the scopes we want.
    for scope in required_scopes:
        if scope not in scopes:
            logger.info("missing scope %s" % scope)
            return False
    return True


def provision_esi_character(char_id, force=False):
    # Get or build Character
    char, created = EVEPlayerCharacter.objects.get_or_create(id=char_id)
    if not created and not force:
        return char

    esi_client = EsiClient()
    character_data, _ = esi_client.get("/v4/characters/%s/" % char_id)

    char.name = character_data["name"]
    char.security_status = character_data.get("security_status")

    char.corporation = EVEPlayerCorporation.get_object(character_data["corporation_id"])
    char.save()

    CcpIdTypeResolver.add_type(char_id, "character")

    return char


def import_eve_character_esi(refresh_token, user, logger=logging.getLogger(__name__)):
    """
    Imports a EVE Character from the ESI API and returns the Character object when completed
    """
    client_id = settings.EVEOAUTH['CONSUMER_KEY']
    base_url = settings.EVEOAUTH['BASE_URL']
    verify_url = base_url + "/verify/"

    # Get character id/name
    token = eve_oauth.get_access_token_from_refresh(refresh_token)

    # check if something went wrong in token exchange
    if token is None:
        return False

    esi_sso = OAuth2Session(client_id, token=token)
    character_data = None
    character_data = esi_sso.get(verify_url).json()
    if 'error' in character_data.keys():
        logger.error("ESI returned invalid data")
        return False

    # This happens when CCP SSO shits the fuck out. It happens more than you may think.
    if character_data is None:
        return False

    character_id = character_data.get('CharacterID')
    character_name = character_data.get('CharacterName')
    owner_hash = character_data.get("CharacterOwnerHash")

    if not character_id or not character_name or not owner_hash:
        # more ccp oauth fuckups
        return False

    alliance_scopes = False
    allied_scopes = False

    scope_list = character_data.get('Scopes', None)
    split_list = scope_list.split(' ')

    if esi_scopes_valid(split_list, settings.ESI_SCOPES):
        alliance_scopes = True
    else:
        if esi_scopes_valid(split_list, settings.ALLIED_ESI_SCOPES):
            allied_scopes = True
        
    if not alliance_scopes and not allied_scopes:
        return None

    # Get or build Character
    character = EVEPlayerCharacter.get_object(character_id)

    # force the character's corporation to update. this is meant to catch new corporations joining TEST
    update_corporation_public_details.delay(character.corporation.pk, throttle_updates=False)

    # DO NOT ISSUE ANY ESI REQUESTS IN THE FOLLOWING BLOCK OF CODE. Any dumb network-related errors that terminate
    # this code prematurely can result in a character with an ESI key that auth thinks is full-scoped, but is only
    # allied scoped.
    character.add_esi_key(
        refresh_token = refresh_token,
        user_adding_key = user,
        current_owner_hash = owner_hash,
        scope_type=ESI_SCOPE_DEFAULT
    )

    scopes = character.esi_scopes
    scopes.reset()

    if alliance_scopes:
        character.authed_as_ally = False
    else:
        character.authed_as_ally = True
    character.save()
    scopes.update_notify_scopes(scope_list)
    # end of critical block

    # if this user does not have a primary character set, do it now
    set_default_primary_character(character)

    update_eve_character_esi.delay(character_id=character.pk)
    return character.pk


def update_character_esi_data(character):

    wallet_balance = get_character_balance(character_ccp_id=character.pk)



    if wallet_balance:
        character.balance = wallet_balance

    character.save()



    character.save()

    return


def set_default_primary_character(character):
    owner = character.owner if character.owner else None
    if owner and owner.profile:
        profile = owner.profile
        # if they don't have a primary character set but do have owned characters
        if profile and not profile.primary_character and profile.associated_characters:
            _ = profile.get_primary_character()  # this sets the default if it doesnt exist, we don't need the retval.


def update_esi_key_roles(character):
    # we need to bypass ESIClient here because we're working directly with SSO
    # if anything goes bad here when talking to SSO, raise an SSOError
    client_id = settings.EVEOAUTH['CONSUMER_KEY']
    base_url = settings.EVEOAUTH['BASE_URL']
    verify_url = base_url + "/verify/"

    token = eve_oauth.get_access_token_from_refresh(character.esi_key)

    # check if something went wrong in token exchange
    if token is None:
        raise EsiError.SsoError("SSO crapped out while updating a character's esi key roles: %s" % character.pk)

    esi_sso = OAuth2Session(client_id, token=token)
    character_data = esi_sso.get(verify_url).json()
    if 'error' in character_data.keys():
        raise EsiError.SsoError("SSO crapped out while updating a character's esi key roles2: %s" % character.pk)

    scope_list = character_data.get('Scopes', None)
    split_list = scope_list.split(' ')

    # ALWAYS USE THE ORIGINAL SCOPES FOR THIS FUNCTION
    alliance_scopes = esi_scopes_valid(split_list, settings.ALLIANCE_LEGACY_ESI_SCOPES)

    scopes = character.esi_scopes
    scopes.reset()

    if alliance_scopes:
        character.authed_as_ally = False
    else:
        character.authed_as_ally = True
    character.save()

    scopes.update_notify_scopes(scope_list)



def update_eve_character_esi(character_id, skip_token_calls=False):
    """
    Updates public character data from the ESI API and returns the Character object when completed
    CACHE - 3600 seconds
    SCOPES - None
    """
    logger.info("starting update for %s" % character_id)
    character = EVEPlayerCharacter.get_object(character_id)
    # todo: update corp history, attributes, etc as seen in import_eve_character_func

    # update public data
    client = EsiClient()
    character_data, _ = client.get("/v4/characters/%s/" % character.pk)

    corp_id = character_data['corporation_id']
    corp = EVEPlayerCorporation.get_object(corp_id)
    character.security_status = character_data.get("security_status")

    character.corporation = corp
    character.save()

    if waffle.switch_is_active('esi-set-default-primary-character'):
        set_default_primary_character(character)

    # see if we can update private data
    if character.esi_key and not skip_token_calls:
        client = EsiClient(authenticating_character=character)
        token, error = client.get_access_token()
        if not error:
            # nothing bad happened, lets update the character's esi_key_last_validated
            character.esi_key_last_validated = timezone.now()
            character.save()

            # reset the ESI key's roles and repopulate them. Only use this if there's been problems with keys getting
            # assigned incorrect permissions
            if waffle.switch_is_active('esi-renew-key-roles-every-update'):
                update_esi_key_roles(character)

            # try to populate esi key's scopes
            character._esi_roles = character.esi_scopes
            character.save()

            # skill/attrib/sp update
            try:
                update_character_esi_data(character)
            except Exception as ex:
                logger.exception("Error updating ESI character %s" % (ex))
                pass



        else:
            if error is EsiError.InvalidRefreshToken:
                logger.info("It looks like the user's esi token was rejected. updating services %s " % character.owner.username)
                # token removal is handled by EsiClient itself. all we need to do now is update user access
                #update_user_access.delay(user=character.owner.id)
                return None
            elif error is EsiError.EsiNotResponding:
                logger.info("ESI query seems to have timed out")
                return None
            elif error is EsiError.ConnectionError:
                logger.info("ESI connection failed")
                return None
            elif error is EsiError.SsoError:
                logger.info("SSO is shitting itself")
                return None
            else:
                logger.warning("an unknown error was triggered when grabbing user access token err: %s char: %s" % (error, character.pk))
                return None

    # update the character's corporation details
    update_corporation_public_details(character.corporation.pk, throttle_updates=True)
    
    return character

