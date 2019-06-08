from django.db import models, IntegrityError
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import User
from django.utils import timezone
import logging, pytz
from datetime import datetime
from eve_api import esi_exceptions, utils
from django.conf import settings
from eve_api.app_defines import *
from eve_api.esi_client import EsiClient
from eve_api.app_defines import ESI_KEY_DELETED_BY_EVEOAUTH, ESI_KEY_REPLACED_BY_OWNER
from django.core.cache import cache
from .esi_models import CharacterESIRoles
import waffle
import logging
import dateutil.parser
from django.apps import apps


class CharacterAssociation(models.Model):
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    character = models.ForeignKey(
        "EVEPlayerCharacter",
        verbose_name="Character",
        on_delete=models.CASCADE
    )

    owner_hash = models.CharField(
        max_length=190,
        verbose_name="Account Owner Hash",
        help_text="This hash is provided by CCP to identify when a character has been transferred to another account. \
        Other characters on the same account will have different account hashes, so don't use this for identifying \
        accounts, only character xfers."
    )


    date_created = models.DateTimeField(auto_now_add=True)
    date_last_login = models.DateTimeField(auto_now_add=True)

    association_active = models.BooleanField(default=True)

    class Meta:
        index_together = [
            ["character", "owner_hash",'association_active'],
        ]

    def __unicode__(self):
        return u"Association between char {} and user {}".format(str(self.character), str(self.owner))

    def __str__(self):
        return self.__unicode__()



class EsiKey(models.Model):
    _esi_roles = models.ForeignKey(CharacterESIRoles, null=True, on_delete=models.CASCADE)

    owner = models.ForeignKey(
        User,
        null = True,
        default = None,
        related_name="esi_key_creator",
        verbose_name="Key Creator",
        help_text="User who created this ESI key",
        on_delete=models.CASCADE
    )

    character = models.ForeignKey(
        "EVEPlayerCharacter",
        default=None,
        null=True,
        related_name="key",
        verbose_name="Character",
        on_delete=models.CASCADE
    )

    refresh_token = models.CharField(
        max_length=512,
        null = True,
        default = None,
        verbose_name="ESI Refresh Token/Key"
    )

    esi_key_last_validated = models.DateTimeField(
        null = True,
        auto_now_add=True,
        verbose_name = "Date ESI key Last Validated"
    )

    esi_key_added = models.DateTimeField(
        null = True,
        auto_now_add=True,
        verbose_name = "Date ESI key Added"
    )

    owner_hash = models.CharField(
        max_length=190,
        default=None,
        null=True,
        verbose_name="Account Owner Hash",
        help_text="This hash is provided by CCP to identify when a character has been transferred to another account. \
        Other characters on the same account will have different account hashes, so don't use this for identifying \
        accounts, only character xfers."
    )

    use_key = models.BooleanField(default=True)


    @staticmethod
    def add_esi_key(char, refresh_token, user_adding_key, current_owner_hash, scopes):

        # first off, obliterate all old keys for this character.
        old_keys = EsiKey.objects.filter(character=char, use_key=True)
        for key in old_keys:
            key.use_key = False
            key.save()


        new_key = EsiKey(
            owner = user_adding_key,
            refresh_token = refresh_token,
            character = char,
            owner_hash = current_owner_hash
        )
        new_key.save()

        # manually provision scopes
        obj, created = CharacterESIRoles.objects.get_or_create(key=new_key)
        obj.update_notify_scopes(scopes)
        return new_key


    def has_esi_scope(self, scope):
        roles = self.esi_scopes
        return roles.has_scopes(scope)

    def provision_esi_scopes(self, obj):
        from eve_api.esi_client import EsiClient
        client = EsiClient(authenticating_character=self.character)
        character_info, _ = client.get('/verify')
        obj.update_notify_scopes(character_info.get('Scopes'))

    @property
    def esi_scopes(self):
        obj, created = CharacterESIRoles.objects.get_or_create(key=self)
        if created:
            self._esi_roles = obj
            self.provision_esi_scopes(obj)
            self.save()

        return obj

    @staticmethod
    def does_user_have_access(user, character_id):
        return EsiKey.objects.filter(character__id = character_id, owner=user, use_key=True).exists()

    @staticmethod
    def does_character_have_key(character_id):
        return EsiKey.objects.filter(character__id=character_id, use_key=True).exists()