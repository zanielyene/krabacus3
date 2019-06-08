from django.core import serializers
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.views.generic import DeleteView, View, UpdateView
from django.views.generic.detail import SingleObjectMixin
from django.contrib import messages
from django.conf import settings
from django.urls import reverse, reverse_lazy
import logging
from braces.views import LoginRequiredMixin
from requests_oauthlib import OAuth2Session
from eve_api.esi_exceptions import EsiDuplicateCharacterExists,EsiDuplicateXMLCharacterExists

from eve_api.tasks import import_eve_character_esi, update_eve_character_esi

import oauthlib.oauth2.rfc6749.errors as oauth_errors

logger=logging.getLogger(__name__)

class EVEESILoginView(View):

    def get(self, request, *args, **kwargs):
        client_id = settings.EVEOAUTH['CONSUMER_KEY']
        base_url = settings.EVEOAUTH['BASE_URL']
        auth_url = base_url + settings.EVEOAUTH['AUTHORIZATION_URL']

        redirect_uri = request.build_absolute_uri(reverse('eve_api:eveapi-esi-callback'))
        scopes = " ".join([s.decode('utf-8') for s in settings.ESI_SCOPES])

        esi_sso = OAuth2Session(client_id, redirect_uri=redirect_uri, scope=scopes)
        authorization_url, state = esi_sso.authorization_url(auth_url)

        request.session['oauth_state'] = state

        return HttpResponseRedirect(authorization_url)

class EVEESIAlliesLoginView(LoginRequiredMixin, View):

    def get(self, request, *args, **kwargs):
        client_id = settings.EVEOAUTH['CONSUMER_KEY']
        base_url = settings.EVEOAUTH['BASE_URL']
        auth_url = base_url + settings.EVEOAUTH['AUTHORIZATION_URL']

        redirect_uri = request.build_absolute_uri(reverse('eve_api:eveapi-esi-callback'))
        scopes = " ".join([s.decode('utf-8') for s in settings.ALLIED_ESI_SCOPES])

        esi_sso = OAuth2Session(client_id, redirect_uri=redirect_uri, scope=scopes)
        authorization_url, state = esi_sso.authorization_url(auth_url)

        request.session['oauth_state'] = state

        return HttpResponseRedirect(authorization_url)


class EVEESICallbackView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        client_id = settings.EVEOAUTH['CONSUMER_KEY']
        client_secret = settings.EVEOAUTH['CONSUMER_SECRET']
        base_url = settings.EVEOAUTH['BASE_URL']
        token_url = base_url + settings.EVEOAUTH['TOKEN_URL']

        redirect_uri = request.build_absolute_uri(reverse('eve_api:eveapi-esi-callback'))

        esi_sso = OAuth2Session(client_id, redirect_uri=redirect_uri, state=request.session['oauth_state'])

        try:
            token = esi_sso.fetch_token(token_url,
                                        authorization_response=redirect_uri+"?"+request.META['QUERY_STRING'],
                                        method='POST',
                                        auth=(client_id, client_secret))
        except oauth_errors.InvalidRequestError:
            messages.error(self.request,
                           "Failed to add character due to CCP Error. Please try again.")
            return HttpResponseRedirect(reverse_lazy('sso:home'))

        access_token = token[u'access_token']
        refresh_token = token[u'refresh_token']

        esi_task_kwargs = {'refresh_token': refresh_token, 'user': self.request.user}

        try:
            task = import_eve_character_esi.apply_async(kwargs=esi_task_kwargs, queue='fastresponse', retry=False)
            out = task.wait(10)
        except celery.exceptions.TimeoutError:
            messages.info(self.request, "The addition of your character is still processing, please check back in a minute or so.")
        except EsiDuplicateXMLCharacterExists:
            messages.error(self.request,"There was an issue registering this Character to our account.")
        except EsiDuplicateCharacterExists:
            messages.error(self.request,"There was an issue registering this character to your account.")
        #except Exception as e :
        #    messages.error(self.request, "An unknown error was encountered while trying to add your character, please try again later.")
        #    logger.error("An unknown error occured while user %s tried to authenticate a character using EVE oauth, exception: %s" % (self.request.user.pk,e))
        #    raise e

        else:
            if out:
                messages.success(self.request, "Character successfully added.")
            else:
                messages.error(self.request, "An issue was encountered while trying to import your character. Something probably broke on CCP's side. Please try again")
        return HttpResponseRedirect(reverse_lazy('sso:home'))


