import hashlib
import logging
from django.conf import settings
from django.core.cache import cache
from requests_oauthlib import OAuth2Session
from oauthlib.oauth2.rfc6749.errors import *


def get_access_token_from_refresh(refresh_token):
    """
    Gets an access token for the given refresh token. Access tokens are cached.
    If an oauth exception occurs, it is passed up.
    ONLY USE THIS FUNCTION TO IMPORT EVE CHARACTER ESI KEYS LIKE IN import_eve_character_esi.
    IF YOU'RE NOT IMPORTING AN ESI KEY, USE EsiClient(authenticating_character=char)
    :param refresh_token:
    :return: access token if success, None if fail
    """
    logger = logging.getLogger(__name__)

    try:
        # Check cache
        refresh_hash = hashlib.sha224(refresh_token).hexdigest()
        access_token = cache.get(refresh_hash)
        if access_token is not None:
            logger.info("Access token request hit cache")
            return access_token
        logger.info("Access token request MISS cache")

        # Get access token from EVE SSO
        client_id = settings.EVEOAUTH['CONSUMER_KEY']
        client_secret = settings.EVEOAUTH['CONSUMER_SECRET']
        base_url = settings.EVEOAUTH['BASE_URL']
        token_url = base_url + settings.EVEOAUTH['TOKEN_URL']

        esi_sso = OAuth2Session(client_id, token={'refresh_token': refresh_token})
        extra = {'client_id': client_id, 'client_secret': client_secret}
        logger.debug("Querying EVE SSO for an access token")
        access_token = esi_sso.refresh_token(token_url, **extra)
        logger.debug("Access token acquired")

        # Add access token to cache
        # Expire the token 30 seconds early so there's no weird race conditions.
        expires_in = int(access_token["expires_in"]) - 30
        cache.set(refresh_hash, access_token, timeout = expires_in)
        logger.debug("Access token added to redis")
        return access_token
    except MissingTokenError:
        # ccp sso shitting out, big surprises
        return None




