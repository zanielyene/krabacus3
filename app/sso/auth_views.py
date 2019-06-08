from django.core import serializers
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.views.generic import DeleteView, View, UpdateView, TemplateView
from django.views.generic.detail import SingleObjectMixin
from django.contrib import messages
from django.conf import settings
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
import random
from eve_api import eve_oauth
import logging
from .models import SSOUser
from braces.views import LoginRequiredMixin
from requests_oauthlib import OAuth2Session
from eve_api.esi_exceptions import EsiDuplicateCharacterExists,EsiDuplicateXMLCharacterExists

from eve_api.tasks import import_eve_character_esi, update_eve_character_esi
from eve_api.models import EsiKey, CharacterAssociation, EVEPlayerCharacter
import oauthlib.oauth2.rfc6749.errors as oauth_errors

logger=logging.getLogger(__name__)

class EsiLoginAsAuthenticationView(View):

    def get(self, request, *args, **kwargs):
        client_id = settings.EVEOAUTH['CONSUMER_KEY']
        base_url = settings.EVEOAUTH['BASE_URL']
        auth_url = base_url + settings.EVEOAUTH['AUTHORIZATION_URL']

        redirect_uri = request.build_absolute_uri(reverse('sso:esi-login-callback'))
        #scopes = " ".join([s.decode('utf-8') for s in settings.ESI_SCOPES])

        esi_sso = OAuth2Session(client_id, redirect_uri=redirect_uri, scope=[])
        authorization_url, state = esi_sso.authorization_url(auth_url)

        request.session['oauth_state'] = state

        return HttpResponseRedirect(authorization_url)


class EsiLoginToAddKeyView(View):

    def get(self, request, *args, **kwargs):
        client_id = settings.EVEOAUTH['CONSUMER_KEY']
        base_url = settings.EVEOAUTH['BASE_URL']
        auth_url = base_url + settings.EVEOAUTH['AUTHORIZATION_URL']

        redirect_uri = request.build_absolute_uri(reverse('sso:esi-login-callback'))
        scopes = " ".join([s for s in settings.ESI_SCOPES])

        esi_sso = OAuth2Session(client_id, redirect_uri=redirect_uri, scope=scopes)
        authorization_url, state = esi_sso.authorization_url(auth_url)

        request.session['oauth_state'] = state

        return HttpResponseRedirect(authorization_url)


class EsiLoginCallbackView(View):
    def get(self, request, *args, **kwargs):
        client_id = settings.EVEOAUTH['CONSUMER_KEY']
        client_secret = settings.EVEOAUTH['CONSUMER_SECRET']
        base_url = settings.EVEOAUTH['BASE_URL']
        token_url = base_url + settings.EVEOAUTH['TOKEN_URL']
        verify_url = base_url + "/verify/"

        redirect_uri = request.build_absolute_uri(reverse('sso:esi-login-callback'))

        esi_sso = OAuth2Session(client_id, redirect_uri=redirect_uri, state=request.session['oauth_state'])

        try:
            token = esi_sso.fetch_token(token_url,
                                        authorization_response=redirect_uri+"?"+request.META['QUERY_STRING'],
                                        method='POST',
                                        auth=(client_id, client_secret))
        except oauth_errors.InvalidRequestError:
            messages.error(self.request,
                           "Failed to add character due to CCP Error. Please try again.")
            return HttpResponseRedirect(reverse('sso:home'))


        sso_data = esi_sso.get(verify_url).json()

        if request.user.is_anonymous:
            # process this as a login
            is_new_user = process_user_login(request, sso_data)
            if is_new_user:
                return HttpResponseRedirect(reverse('sso:profilefirst'))
            else:
                return HttpResponseRedirect(reverse('sso:profile'))
        else:
            # process this as a key addition
            name = process_key_addition(request, sso_data, token["refresh_token"])
            # todo: maybe "closing in 5 seconds" page
            messages.info(request, "Successfully added {}'s ESI key".format(name))
            return HttpResponseRedirect(reverse('sso:key-add-success'))

        return HttpResponseRedirect(reverse('sso:profile'))


def get_or_create_character_association(char, owner_hash, user):
    """
    provisions character associations to users.
    If character association exists attached to another user, this will deactivate
    the old association.
    :param char_id:
    :param owner_hash:
    :param user:
    :return:
    """

    # check for an existing association for any OTHER user
    belongs_to_user_logged_in = CharacterAssociation.objects.filter(
        character=char,
        association_active=True,
        owner=user,
        owner_hash = owner_hash
    ).exists()

    if belongs_to_user_logged_in:
        # update date_last_login
        association = CharacterAssociation.objects.filter(
            character=char,
            association_active=True,
            owner=user,
            owner_hash = owner_hash
        ).first()
        association.date_last_login = timezone.now()
        association.save()
        return association

    # char doesn't belong to the currently logged in user.
    # we need to delete any old associations and create a new one
    old_associations = CharacterAssociation.objects.filter(
        character=char,
        association_active=True
    )

    for association in old_associations:
        association.association_active=False
        association.save()

    # now create a new one
    association = CharacterAssociation(
        owner = user,
        character = char,
        owner_hash = owner_hash
    )
    association.save()
    return association



def process_key_addition(request, sso_data, refresh_token):
    char_id = int(sso_data["CharacterID"])
    owner_hash = sso_data["CharacterOwnerHash"]
    scope_list = sso_data.get('Scopes', None)
    if not scope_list:
        raise Exception("no scopes provided")

    for scope in settings.ESI_SCOPES:
        if scope not in scope_list:
            raise Exception("not enough scopes provided")

    # make sure we have this char
    c = EVEPlayerCharacter.get_object(char_id)

    # build/get association
    association = get_or_create_character_association(
        c,
        owner_hash,
        request.user
    )

    # create key
    key = EsiKey.add_esi_key(c, refresh_token, request.user, owner_hash, scope_list)
    return c.name


def format_character_name(name):
    name = name.replace(' ','')
    name = name.replace('-', '')
    name = name.replace("'","")
    name = name.lower()
    suffix = random.randint(1000,9999)
    return name + str(suffix)


def create_user_account(char_name, char_id, owner_hash):
    character = EVEPlayerCharacter.get_object(char_id)

    username = format_character_name(char_name)
    user = User.objects.create_user(username)
    user.backend = 'django.contrib.auth.backends.ModelBackend'
    user.save()

    new_association = get_or_create_character_association(
        char = character,
        owner_hash = owner_hash,
        user=user,
    )
    profile = user.profile
    profile.primary_character = character
    profile.save()
    return user


def process_user_login(request, sso_data):
    """
    Returns True if new user, False if existing
    :param request:
    :param sso_data:
    :return:
    """
    has_account = CharacterAssociation.objects.filter(
        character__id=sso_data["CharacterID"],
        owner_hash=sso_data["CharacterOwnerHash"],
        association_active=True,
    ).exists()

    if has_account:
        # update association
        association = CharacterAssociation.objects.get(
            character__id=sso_data["CharacterID"],
            owner_hash=sso_data["CharacterOwnerHash"],
            association_active=True,
        )
        association.date_last_login = timezone.now()
        association.save()
        messages.info(request, "Welcome to Krabacus, {}".format(association.character.name))
        login(request, association.owner)
        return False
    else:
        # we need to provision an account
        user = create_user_account(
            sso_data["CharacterName"],
            sso_data["CharacterID"],
            sso_data["CharacterOwnerHash"])
        messages.info(request, "Welcome to Krabacus, {}. Let's get you set up".format(sso_data["CharacterName"]))
        login(request, user)
        return True

class KeyAddSuccessView(TemplateView):
    template_name =  'sso/key_add_success.html'
