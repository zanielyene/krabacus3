from __future__ import division

import logging
import random
from math import sqrt
import requests
from django.conf import settings
from django.http import HttpResponse
from django.core.cache import cache


from eve_api.esi_client import EsiError
from eve_api.models import EVEPlayerCorporation, EVEPlayerCharacter

logger = logging.getLogger(__name__)







def installed(value):
    apps = settings.INSTALLED_APPS
    if "." in value:
        for app in apps:
            if app == value:
                return True
    else:
        for app in apps:
            fields = app.split(".")
            if fields[-1] == value:
                return True
    return False

