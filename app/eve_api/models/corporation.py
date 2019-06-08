import logging
import waffle
from django.db import models, IntegrityError
from django.db.models import Q
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver
from eve_api.app_defines import *


class EVEPlayerCorporation(models.Model):
    """
    Represents a player-controlled corporation. Updated from a mixture of
    the alliance and corporation API pullers.
    """
    name = models.CharField(max_length=255, blank=True, null=True)
    ticker = models.CharField(max_length=15, blank=True, null=True)
    alliance = models.ForeignKey('eve_api.EVEPlayerAlliance', blank=True, null=True, on_delete=models.CASCADE)

    @staticmethod
    def get_object(ccp_id):
        try:
            item = EVEPlayerCorporation.objects.get(pk=ccp_id)
        except Exception as e:
            EVEPlayerCorporation.verify_object_exists(ccp_id)
            return EVEPlayerCorporation.objects.get(pk=ccp_id)
        # check for legacy side case where the corporation was partially imported
        if item.name is None:
            from eve_api.tasks.esi_corporation import provision_esi_corporation
            c = provision_esi_corporation(ccp_id, force=True)
            assert (c.name is not None)
            return c
        return item

    @staticmethod
    def import_object(ccp_id):
        try:
            from eve_api.tasks.esi_corporation import provision_esi_corporation
            provision_esi_corporation(ccp_id)
        except IntegrityError:
            pass

    @staticmethod
    def verify_object_exists(ccp_id):
        # check cache
        exists = cache.get("eveplayercorporation_exists_%s" % ccp_id)
        if exists:
            return

        exists = EVEPlayerCorporation.objects.filter(pk=ccp_id).exists()
        if not exists:
            EVEPlayerCorporation.import_object(ccp_id)

        # should exist by this point, set cache
        cache.set("eveplayercorporation_exists_%s" % ccp_id, True, timeout=86400)

    @property
    def printable_name(self):
        if self.name is None:
            return "Corp #" + str(self.pk)
        else:
            return self.name

    @property
    def printable_alliance_name(self):
        if self.alliance is None:
            return ""
        else:
            return self.alliance.printable_name

    class Meta:
        app_label = 'eve_api'
        verbose_name = 'Corporation'
        verbose_name_plural = 'Corporations'
        select_on_save = True

    def __unicode__(self):
        if self.name:
            return self.name
        else:
            return u"Corp #%d" % self.id


@receiver(post_save, sender=EVEPlayerCorporation)
def corp_cache_invalidator(sender, instance, **kwargs):
    corp_id = instance.pk
    keys = [x.format(corp_id) for x in ['corporation_affiliation_{}', 'eveplayercorporation_exists_{}']]
    cache.delete_many(keys)
