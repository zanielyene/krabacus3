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

logger=logging.getLogger(__name__)


class EVEPlayerCharacter(models.Model):
    """
    Represents an individual player character within the game. Not to be
    confused with an account.
    """
    name = models.CharField(max_length=255, blank=True, null=False)
    corporation = models.ForeignKey('eve_api.EVEPlayerCorporation', blank=True, null=True, on_delete=models.CASCADE)

    orders_last_updated = models.DateTimeField(default=None,null=True)
    assets_last_updated = models.DateTimeField(default=None, null=True)
    transactions_last_updated = models.DateTimeField(default=None, null=True)
    journal_last_updated = models.DateTimeField(default=None, null=True)

    def delete_revoked_esi_key(self):
        keys = self.key.filter(use_key=True)
        logger.info("Deleting {} revoked keys for {}".format(len(keys), self.name))
        for key in keys:
            key.use_key = False
            key.save()
        return

    @staticmethod
    def get_object(ccp_id):
        try:
            item = EVEPlayerCharacter.objects.get(pk=ccp_id)

            # check for legacy characters that auth never imported a corporation for
            if ccp_id != 1:
                if item.corporation is None:
                    from eve_api.tasks import provision_esi_character
                    provision_esi_character(ccp_id, force=True)
                # check for another legacy sidecase where a corporation was partially imported
                elif item.corporation.name is None:
                    from eve_api.models import EVEPlayerCorporation
                    EVEPlayerCorporation.get_object(item.corporation.pk)
                item = EVEPlayerCharacter.objects.get(pk=ccp_id)

            return item
        except ObjectDoesNotExist:
            EVEPlayerCharacter.verify_object_exists(ccp_id)
            return EVEPlayerCharacter.objects.get(pk=ccp_id)

    @staticmethod
    def import_object(ccp_id):
        from eve_api.tasks import provision_esi_character
        provision_esi_character(ccp_id)

    @staticmethod
    def verify_object_exists(ccp_id):
        # check cache
        exists = cache.get("eveplayercharacter_exists_%s" % ccp_id)
        if exists:
            return True

        exists = EVEPlayerCharacter.objects.filter(pk=ccp_id).exists()
        if not exists:
            if int(ccp_id) == 1:
                # this id refers to the EVE System itself.
                from eve_api.models.corporation import EVEPlayerCorporation
                corp, created = EVEPlayerCorporation.objects.get_or_create(id=1)
                if created:
                    corp.name = "EVE System"
                    corp.ticker = "EVE"
                    corp.save()


                char = EVEPlayerCharacter(
                    pk=1,
                    name="EVE Online (Tranquility)",
                    corporation=corp
                )
                char.save()
            else:
                EVEPlayerCharacter.import_object(ccp_id)

        # no matter what happens the chraracter should be imported by now, so set cache
        cache.set("eveplayercharacter_exists_%s" % ccp_id, True, timeout=86400)

    @property
    def owner(self):
        raise NotImplementedError()
        if hasattr(self, 'owner') and self.owner is not None:
            return self.owner
        elif hasattr(self, 'eveaccount') and self.eveaccount is not None:
            return self.eveaccount.user


    @property
    def director(self):
        """ Returns a bool to indicate if the character is a director """
        director_roles = ['roleDirector', 'Director']  # Different names for XML and ESI
        # if no esi key, assume we cant rely on roles
        if self.esi_key_may_grant_services is None:
            return False

        for r in director_roles:
            try:
                role = self.roles.get(name=r)
                return True
            except ObjectDoesNotExist:
                pass
        return False

    @property
    def station_manager(self):
        """ Returns a bool to indicate if the character is a station manager """
        stationmanager_roles = ['roleStationManager', 'Station_Manager']  # Different names for XML and ESI
        # if no esi key, assume we cant rely on roles
        if self.esi_key_may_grant_services is None:
            return False

        for r in stationmanager_roles:
            try:
                role = self.roles.get(name=r)
                return True
            except ObjectDoesNotExist:
                pass
        return False

    @property
    def printable_name(self):
        if self.name is None:
            return "Char #" + str(self.pk)
        else:
            return self.name

    @property
    def printable_corp_name(self):
        if self.corporation is None:
            return ""
        else:
            return self.corporation.printable_name

    @property
    def printable_alliance_name(self):
        if self.corporation is None:
            return ""
        elif self.corporation.alliance is None:
            return ""
        else:
            return self.corporation.alliance.printable_name


    def __unicode__(self):
        if self.name:
            return self.name
        else:
            return u"(%d)" % self.id

    def __str__(self):
        return self.__unicode__()

    class Meta:
        app_label = 'eve_api'
        verbose_name = 'Character'
        verbose_name_plural = 'Characters'
        select_on_save = True
