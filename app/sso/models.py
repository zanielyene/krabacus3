from datetime import datetime, timedelta
import types
import hashlib

from django.db import models
from django.db.models import signals
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.conf import settings
from django.utils import timezone


from eve_api.models import EVEPlayerCharacter
from eve_api.models import EVEPlayerCharacter

from notifications.models import UpdateMessage, UpdateMessageReadReceipt

import waffle

from operator import itemgetter

## Exceptions





class SSOUser(models.Model):
    """ Extended SSO User Profile options """

    user = models.OneToOneField(User, related_name="profile", on_delete=models.CASCADE)
    primary_character = models.ForeignKey(EVEPlayerCharacter,null=True, default=None, on_delete=models.CASCADE)
    def __unicode__(self):
        return self.user.__unicode__()

    @property
    def get_primary_character(self):
        return "lol"

    @staticmethod
    def create_user_profile(sender, instance, created, **kwargs):
        if created:
            profile, created = SSOUser.objects.get_or_create(user=instance)

            # create notification receipts
            all_messages = UpdateMessage.objects.all()
            read_receipts = []
            for message in all_messages:
                read_receipts.append(
                    UpdateMessageReadReceipt(
                        user = instance,
                        message = message,
                    )
                )
            UpdateMessageReadReceipt.objects.bulk_create(read_receipts)



signals.post_save.connect(SSOUser.create_user_profile, sender=User)



