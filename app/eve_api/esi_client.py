import logging
import json
import requests
import time
import datetime
import pytz
import email.utils as eut
import enum
import hashlib
import waffle

# we really really dont want to import this sanely or else monkey patch will trigger twice
from manage import grequests

from django.conf import settings
from django.core.cache import cache
from django.apps import apps

from oauthlib.common import urldecode
from oauthlib.oauth2.rfc6749.errors import *
from requests.adapters import HTTPAdapter
from requests_oauthlib import OAuth2Session
from simplejson import JSONDecodeError
from urllib3.util.retry import Retry
from raven import breadcrumbs

logger=logging.getLogger(__name__)


class EsiError(enum.Enum):
    ConnectionError = 1
    InvalidRefreshToken = 2
    EsiNotResponding = 3
    SsoError = 4
    EsiApplicationError = 5


class EsiClient():
    def __init__(self,
                 authenticating_character=None,
                 max_retries = settings.MAX_ESI_RETRIES,
                 log_application_errors=True,
                 raise_application_errors=True,
                 raise_other_errors=True,
                 error_throttle_threshold=20,
                 bypass_cache=False,
                 retry_interval_seconds=settings.ESI_RETRY_TIME_INTERVAL_SECONDS
                 ):
        self._max_retries = max_retries
        self._log_application_errors = log_application_errors
        self._authenticating_character = authenticating_character
        self._raise_application_errors = raise_application_errors
        self._raise_other_errors = raise_other_errors
        self._error_throttle_threshold = error_throttle_threshold
        self._bypass_cache = bypass_cache
        self._retry_interval_seconds = retry_interval_seconds

        # contains x-headers of most recent esi request made with this client
        self._x_headers = {}

    @staticmethod
    def is_refresh_token_valid(refresh_token):
        client_id = settings.EVEOAUTH['CONSUMER_KEY']
        client_secret = settings.EVEOAUTH['CONSUMER_SECRET']
        headers = {
            'Accept': 'application/json',
            'Content-Type': (
                'application/x-www-form-urlencoded;charset=UTF-8'
            ),
        }
        body = "grant_type=refresh_token&client_secret=%s&client_id=%s&refresh_token=%s" % (client_secret, client_id, refresh_token)
        token_url = settings.EVEOAUTH['BASE_URL'] + settings.EVEOAUTH['TOKEN_URL']
        session = requests.Session()

        r = session.post(token_url, data=dict(urldecode(body)), headers=headers)
        logger.debug('Request to fetch token completed with status %s.',r.status_code)
        logger.debug('Request headers were %s', r.request.headers)
        logger.debug('Request body was %s', r.request.body)
        logger.debug('Response headers were %s and content %s.',r.headers, r.text)

        #breadcrumbs.record('Request to fetch token completed with status %s.',r.status_code)
        #breadcrumbs.record('Request headers were %s', r.request.headers)
        #breadcrumbs.record('Request body was %s', r.request.body)
        #breadcrumbs.record('Response headers were %s and content %s.',r.headers, r.text)

        if r.text:
            try:
                content = json.loads(r.text)
                if "error" in content:
                    if content["error"] == "invalid_token":
                        return False
            # any exceptions here are purely the fault of CCP oauth, and cannot be used to indicate token validity
            except ValueError:
                return True
        return True

    def _get_access_token_from_refresh(self):
        """
        Returns access token for character defined by self._authenticating character.
        Returns error EsiError.InvalidRefreshToken
        Side effects: revokes character's ESI key if InvalidRefreshToken detected.
        :return: access token, err
        """
        try:
            EsiKey_lazy = apps.get_model(app_label='eve_api', model_name='EsiKey')
            key_exists = EsiKey_lazy.objects.filter(
                character = self._authenticating_character,
                use_key = True
            ).exists()
            if not key_exists:
                raise Exception("We dont have an ESI key for this character")


            key = EsiKey_lazy.objects.filter(character=self._authenticating_character, use_key=True).first()
            refresh_token = key.refresh_token

            # Check cache
            cache_key = hashlib.sha224(refresh_token.encode('utf-8')).hexdigest()
            access_token = cache.get(cache_key)
            if access_token is not None:
                logger.info("Access token request hit cache")
                return access_token, None
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
            cache_key = hashlib.sha224(refresh_token.encode('utf-8')).hexdigest()
            cache.set(cache_key, access_token, timeout=expires_in)
            logger.debug("Access token added to redis")
            return access_token, None
        except OAuth2Error as e:
            # CCP is giving us oauth errors. We need to verify if the user's token is rejected. We do that using a urllib
            # post because we don't trust the error codes being returned by our oauth2 lib
            if not EsiClient.is_refresh_token_valid(refresh_token):
                logger.warning("ESI Refresh Token was rejected. User probably deleted TEST Auth app. exception: InvalidTokenError charid %s charname %s" % (
                    self._authenticating_character.pk, self._authenticating_character.name))
                if waffle.switch_is_active("delete_keys_when_revoked"):
                    self._authenticating_character.delete_revoked_esi_key()
                return None, EsiError.InvalidRefreshToken
            else:
                # assume it's some fucky ccp oauth error.
                logger.warning("Received oauth error %s for char %s " % (e.error, self._authenticating_character.pk))
                # re-raise the exception so it will propagate up stack to trigger retry logic
                raise e
        # allow all other exceptions to propagate up stack to trigger retry logic

    def _update_error_throttle_counter(self, response, endpoint):
        logger = logging.getLogger(__name__)
        if response is None:
            return
        self._x_headers = response.headers
        if "X-Esi-Error-Limit-Remain" in response.headers:
            error_allowance_remaining = int(response.headers["X-Esi-Error-Limit-Remain"])
            if error_allowance_remaining < self._error_throttle_threshold:
                wait_time = int(response.headers["X-Esi-Error-Limit-Reset"])
                logger.warning(
                    "ESI error allowance down to %s after executing %s. Blocking ESI Request for %s seconds." % (
                    error_allowance_remaining, endpoint, wait_time))
                cache.set("BLOCK_ESI_REQUESTS", wait_time, timeout=wait_time + 1)
            else:
                if error_allowance_remaining != 100:
                    logger.info("Esi error allowance is %s" % error_allowance_remaining)

    def _block_if_throttle_active(self):
        block_time = cache.get("BLOCK_ESI_REQUESTS")
        if block_time is not None:
            logger = logging.getLogger(__name__)
            logger.warning("blocking ESI call for %s seconds" % block_time)
            time.sleep(block_time)
        return

    def _prepare_request(self, endpoint_url):
        self._block_if_throttle_active()
        esi_url = settings.EVE_ESI_URL
        full_url = esi_url + endpoint_url

        client_id = settings.EVEOAUTH['CONSUMER_KEY']

        if self._authenticating_character is None:
            esi_session = OAuth2Session(client_id)
            return full_url, None, esi_session
        else:
            access_token, err = self._get_access_token_from_refresh()
            if err is not None:
                return full_url, err, None

            esi_session = OAuth2Session(client_id, token=access_token)
            return full_url, None, esi_session

    def _depreciation_check(self, response, url):
        if "Warning" in response.headers:
            if response.headers["Warning"] == "299 - This route is deprecated.":
                logger.error("Route depreciating soon: %s" % url)

    def _perform_request(self, url, post_body, session):
        if post_body is None:
            response = session.get(url)
        else:
            json_data = json.dumps(post_body)
            headers = {"Content-Type":"application/json"}
            response = session.post(url, data=json_data, headers=headers)

        # update the x-error-limit, no matter what happened with this specific request
        self._update_error_throttle_counter(response, url)
        try:
            data = response.json()
        except JSONDecodeError as e:
            # this is most likely a 502 bad gateway
            resp = response.content
            if "502 Bad Gateway" in resp.decode("ascii"):
                # create a fake data object to represent ESI's unresponsive state
                data = {"error":"failed to proxy request", "actual_error":"502 bad gateway"}
            else:
                logger.error("strange json decode error url: %s response content: %s" % (url, resp))
                raise e

        if type(data) is dict:
            if "error" in data:
                # check for SSO Error
                if "sso_status" in data:
                    logger.warning("SSO Error when querying %s %s returning %s" % (url, post_body,data))
                    return data, EsiError.SsoError, None
                if data["error"] == "The datasource tranquility is temporarily unavailable":
                    logger.warning("Esi not responding (down?) when querying %s %s returning %s" % (url, post_body,data))
                    return data, EsiError.EsiNotResponding, None
                if data["error"] == "No reply within 10 seconds":
                    logger.warning("Esi not responding when querying %s %s returning %s" % (url, post_body,data))
                    return data, EsiError.EsiNotResponding, None
                if data["error"] == "timeout contacting endpoint":
                    logger.warning("Esi timing out when querying %s %s returning %s" % (url, post_body,data))
                    return data, EsiError.EsiNotResponding, None
                if data["error"] == "Unhandled internal error encountered!":
                    logger.warning("ESI throwing unhandled error when querying %s %s returning %s" % (url,post_body, data))
                    return data, EsiError.EsiNotResponding, None
                if data["error"] == "Internal error":
                    logger.warning("ESI throwing unhandled error when querying %s %s returning %s" % (url,post_body, data))
                    return data, EsiError.EsiNotResponding, None
                if data["error"] == "failed to proxy request":
                    logger.warning("ESI throwing unhandled error when querying %s %s returning %s" % (url,post_body, data))
                    return data, EsiError.EsiNotResponding, None
                if data["error"] == "Timeout contacting tranquility":
                    logger.warning("ESI timeout when querying tranquility when querying %s %s returning %s" % (url,post_body, data))
                    return data, EsiError.EsiNotResponding, None
                # can only assume it's an application error at this point
                if self._log_application_errors:
                    logger.warning("ESI threw application error when querying %s %s returning %s" % (url, post_body, data))
                return data, EsiError.EsiApplicationError, None

        expires_at = None
        if "expires" in response.headers:
            expires = eut.parsedate(response.headers["expires"])
            tz = pytz.timezone('UTC')
            expires_at= datetime.datetime(*expires[:6]).replace(tzinfo=tz)

        self._depreciation_check(response, url)
        return data, None, expires_at

    def _post_inner(self, endpoint_url, post_body):
        try:
            url, err, session = self._prepare_request(endpoint_url)
            if err is not None:
                return None, err, None

            data, err, expires_at = self._perform_request(url, post_body, session)
            return data, err, expires_at
        except requests.exceptions.ConnectionError as e:
            logger.warning("Connection error when querying ESI")
            return None, EsiError.ConnectionError, None
        # revoked token oauth errors are handled further down stack, so oauth errors at this point typically indicate
        # that EVE SSO is down
        except OAuth2Error as e:
            logger.warning("miscellanious oauth error %s" % (e.error) )
            return None, EsiError.SsoError, None

    def _get_cache_key(self, endpoint_url, post_body):
        # create a cache key for this data
        # hash keys are composed of endpoint url, post body, and the pk of the authenticating character, if provided
        algo = hashlib.new('SHA256')
        authchar = self._authenticating_character.pk if self._authenticating_character is not None else None
        p_body = post_body if post_body else ""
        a_char = authchar if authchar else ""
        algo.update((str(endpoint_url) + str(p_body) + str(a_char)).encode('utf-8') )
        hash_hexstr = algo.hexdigest()
        k = "esi_cache_%s" % hash_hexstr
        return k[:249]

    def _try_read_from_cache(self, endpoint_url, post_body):
        cache_key = self._get_cache_key(endpoint_url, post_body)
        cached_data = cache.get(cache_key)
        return cached_data

    def _write_to_cache(self, endpoint_url, post_body, content, expires_at):
        #if expires_at is None:
            # we can't cache data that doesnt have a ccp-defined expiry
            #logger.error("the following endpoint isnt giving us an expiry time: %s" % endpoint_url)
        #    return

        cache_key = self._get_cache_key(endpoint_url, post_body)

        cache.set(cache_key, content, timeout=settings.ESI_CACHE_DURATION_SECONDS)
        return

    def post(self, endpoint_url, post_body):
        if not self._bypass_cache and not settings.GLOBALLY_DISABLE_ESI_CACHE:
            data = self._try_read_from_cache(endpoint_url, post_body)
            if data is not None:
                logger.info("hit cache for %s" % endpoint_url)
                return data, None
            logger.info("missed cache for %s" % endpoint_url)

        retries_remaining = self._max_retries
        while retries_remaining > 0:
            data, err, expires_at = self._post_inner(endpoint_url, post_body)
            # these three conditions are not retryable
            if err is None or err == EsiError.EsiApplicationError or err == EsiError.InvalidRefreshToken:
                break
            # all other error conditions are retryable
            retries_remaining -= 1
            logger.warning("Retrying request %s %s after error %s. Retries remaining: %s" % (endpoint_url, post_body, err, retries_remaining))

            time.sleep(self._retry_interval_seconds)

        if err is None:
            self._write_to_cache(endpoint_url, post_body, data, expires_at)
            return data,err
        elif err == EsiError.EsiApplicationError and self._raise_application_errors:
            raise Exception("Esi client received application error when querying %s %s recvd content %s" % (endpoint_url, post_body, data))
        elif err == EsiError.EsiApplicationError and not self._raise_application_errors:
            return data, err
        elif self._raise_other_errors:
            raise Exception("Esi client received connection error when querying %s %s recvd content %s err %s" % (endpoint_url, post_body, data, err))
        else:
            return data, err

    def get(self, endpoint_url):
        return self.post(endpoint_url, post_body=None)

    def get_access_token(self):
        if self._authenticating_character is None:
            return None, None
        try:
            access_token, err = self._get_access_token_from_refresh()
            return access_token, err
        except OAuth2Error as e:
            logger.warning("misc oauth error %s " % e.error)
            return None, EsiError.SsoError
        except requests.exceptions.ConnectionError as e:
            logger.warning("Connection error when querying ESI")
            return None, EsiError.ConnectionError

    def get_page_count(self, endpoint_url):
        cache_setting = self._bypass_cache
        self._bypass_cache = True

        _ = self.post(endpoint_url, post_body=None)
        self._bypass_cache = cache_setting
        pages = self._x_headers.get("X-Pages")
        if pages is None:
            pages = self._x_headers.get("x-pages")
        return int(pages) if pages is not None else None

    def _chunks(self, l, n):
        """Yield successive n-sized chunks from l."""
        for i in range(0, len(l), n):
            yield l[i:i + n]

    def get_multiple(self, endpoint_url, params):
        # no error handling as of right now, mayyyy want to change that
        url, err, session = self._prepare_request(endpoint_url)

        retry = Retry(
            total=3,
            read=3,
            connect=3,
            backoff_factor=0.3,
            status_forcelist=(500, 502, 504),
        )

        # mount a custom ssl adapter that will have a large enough connection pool
        max_pool_size = 128
        pool_size = min(max_pool_size, len(params))
        logger.info("building http adapter with pool size {}".format(pool_size))
        session.mount('https://',
                      HTTPAdapter(
                          pool_connections = pool_size,
                          pool_maxsize= pool_size,
                          max_retries=retry
                      )
                    )
        logger.info("adapter mounted")

        requests = [(grequests.get(url.format(p), session=session),p) for p in params]

        results = {}

        for chunk in self._chunks(requests, max_pool_size):
            logger.debug("mapping chunk")
            request_urls = [r for r,_ in chunk]
            request_params = [p for _,p in chunk]

            responses = grequests.map(request_urls)
            responses_with_params = zip(request_params, responses)
            logger.debug("map completed")

            for param,response in responses_with_params:
                # update the x-error-limit, no matter what happened with this specific request
                # self._update_error_throttle_counter(response, url)

                # no error handling until we can figure out implications
                try:
                    data = response.json()
                except JSONDecodeError as e:
                    logger.error(str(e) + " " + str(response.content))
                    raise e
                if type(data) is dict:
                    if "error" in data:
                        if self._raise_application_errors:
                            raise Exception("bad result from esi: {} with param {} on url {}".format(data, param, endpoint_url))
                self._depreciation_check(response, endpoint_url)

                results[param] = data

        return results

    def get_multiple_paginated(self, endpoint_url):
        page_count = self.get_page_count(endpoint_url)
        #page_count = 0 if page_count is None else page_count
        expires = self._x_headers.get("expires")

        params = [i+1 for i in range(page_count)]

        results = self.get_multiple_flat(endpoint_url + "?page={}", params, expiry=expires, return_if_cache_inconsistent=True)
        if results is None:
            # cache failure, we need to restart
            return self.get_multiple_paginated(endpoint_url)
        else:
            return results

    def get_multiple_flat(self, endpoint_url, params, expiry=None, return_if_cache_inconsistent=False):
        # no error handling as of right now, mayyyy want to change that
        url, err, session = self._prepare_request(endpoint_url)

        retry = Retry(
            total=3,
            read=3,
            connect=3,
            backoff_factor=0.3,
            status_forcelist=(500, 502, 504),
        )

        # mount a custom ssl adapter that will have a large enough connection pool
        max_pool_size = 128
        pool_size = min(max_pool_size, len(params))
        logger.info("building http adapter with pool size {}".format(pool_size))
        session.mount('https://',
                      HTTPAdapter(
                          pool_connections = pool_size,
                          pool_maxsize= pool_size,
                          max_retries=retry
                      )
                    )
        logger.info("adapter mounted")

        requests = [(grequests.get(url.format(p), session=session),p) for p in params]

        results = []

        c_id = 0
        for chunk in self._chunks(requests, max_pool_size):
            logger.info("mapping chunk")
            request_urls = [r for r,_ in chunk]

            responses = grequests.map(request_urls)
            logger.info("map completed")
            r_id = 0
            for response in responses:
                if expiry is None:
                    expiry = response.headers["expires"]
                else:
                    if expiry != response.headers["expires"]:
                        # a cache switchover happened somewhere in here. WE NEED TO REDO EVERYTHING.
                        logger.warning("Cache switchover while querying {}. Restarting query.".format(endpoint_url))
                        if return_if_cache_inconsistent:
                            return None
                        else:
                            return self.get_multiple_flat(endpoint_url, params)

                data = response.json()

                r_id += 1
                results.extend(data)
            c_id += 1
            # run a single depreciation check
            if responses:
                self._depreciation_check(responses[0], endpoint_url)

        return results


