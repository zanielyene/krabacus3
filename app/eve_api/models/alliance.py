from django.db import models, IntegrityError
from django.contrib.auth.models import Group
from django.core.cache import cache

class EVEPlayerAlliance(models.Model):
    """
    Represents a player-controlled alliance. Updated from the alliance
    EVE XML API puller at intervals.
    """
    name = models.CharField(max_length=255, blank=True, null=False)
    ticker = models.CharField(max_length=15, blank=True, null=False)


    class Meta:
        app_label = 'eve_api'
        verbose_name = 'Alliance'
        verbose_name_plural = 'Alliances'
        select_on_save = True

    def __unicode__(self):
        if self.name:
            return self.name
        else:
            return "(#%d)" % self.id


    @staticmethod
    def get_object(ccp_id):
        try:
            item = EVEPlayerAlliance.objects.get(pk=ccp_id)
            return item
        except Exception as e:
            EVEPlayerAlliance.verify_object_exists(ccp_id)
            return EVEPlayerAlliance.objects.get(pk=ccp_id)

    @staticmethod
    def import_object(ccp_id):
        try:
            from eve_api.tasks.esi_alliance import provision_esi_alliance
            provision_esi_alliance(ccp_id)
        except IntegrityError:
            pass

    @staticmethod
    def verify_object_exists(ccp_id):
        # check cache
        exists = cache.get("eveplayeralliance_exists_%s" % ccp_id)
        if exists:
            return

        exists = EVEPlayerAlliance.objects.filter(pk=ccp_id).exists()
        if not exists:
            EVEPlayerAlliance.import_object(ccp_id)

        cache.set("eveplayeralliance_exists_%s" % ccp_id, True, timeout=86400)


    @property
    def printable_name(self):
        if self.name is None:
            return "Alliance #" + str(self.pk)
        else:
            return self.name
