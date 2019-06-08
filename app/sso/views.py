import hashlib
import logging
import random
import re
import unicodedata
from operator import attrgetter, itemgetter

import oauthlib.oauth2.rfc6749.errors as oauth_errors
import waffle
from django.conf import settings
from requests_oauthlib import OAuth2Session
import requests
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.urls import reverse, reverse_lazy
from django.db.models import FloatField, Q, Sum
from django.http import (HttpResponseForbidden, HttpResponseNotFound,
                         HttpResponseRedirect, JsonResponse)
from django.shortcuts import get_object_or_404, redirect
from django.template import RequestContext
from braces.views import LoginRequiredMixin, PermissionRequiredMixin

from eve_api.tasks import update_eve_character_esi

from django.views.decorators.csrf import csrf_exempt
from django.views.generic import (DetailView, FormView, ListView, TemplateView,
                                  View)
from market.models import TradingRoute
from eve_api.models import CharacterAssociation, EsiKey

from django.core.exceptions import PermissionDenied
from .models import SSOUser
logger=logging.getLogger(__name__)


class ProfileView(TemplateView):
    template_name = 'sso/profile.html'

    def get(self, request, *args, **kwargs):

        return super(ProfileView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super(ProfileView, self).get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            routes = TradingRoute.objects.filter(creator=self.request.user)
            ctx["routes"] = routes

        return ctx


class AnalyticsView(TemplateView):
    template_name = 'sso/analytics.html'

    def get(self, request, *args, **kwargs):

        return super(AnalyticsView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super(AnalyticsView, self).get_context_data(**kwargs)
        if self.request.user.is_authenticated and self.request.user.is_superuser:
            users = User.objects.all()
            users_with_no_routes = []
            users_with_routes = []

            for u in users:
                if not TradingRoute.objects.filter(creator=u).exists():
                    # get number of esi chars
                    chars = EsiKey.objects.filter(owner=u, use_key=True)
                    users_with_no_routes.append({
                        "user": u,
                        "num_keys": len(chars)
                    })
                else:
                    routes = TradingRoute.objects.filter(creator=u)
                    most_recent = routes.filter(last_viewed__isnull=False).order_by('-last_viewed')
                    if not most_recent:
                        most_recent = None
                        last_viewed = None
                    else:
                        most_recent = most_recent[0]
                        last_viewed = most_recent.last_viewed

                    users_with_routes.append({
                        "user":u,
                        "num_routes": len(routes),
                        "most_recent_viewed": most_recent,
                        "most_recent_view_time": last_viewed
                    })
            ctx["users_with_routes"] = users_with_routes
            ctx["users_with_no_routes"] = users_with_no_routes
        else:
            raise PermissionDenied()

        return ctx

class AccountView(TemplateView):
    template_name = 'sso/account.html'

    def get(self, request, *args, **kwargs):

        return super(AccountView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super(AccountView, self).get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            characters = CharacterAssociation.objects.filter(owner = self.request.user, association_active=True)
            characters_with_keys = []
            characters_without_keys = []
            for association in characters:
                has_key = EsiKey.does_character_have_key(association.character.pk)
                if has_key:
                    characters_with_keys.append(association.character)
                else:
                    characters_without_keys.append(association.character)
            ctx["characters_with_keys"] = characters_with_keys
            ctx["characters_without_keys"] = characters_without_keys
            ctx["subscription"] = self.request.user.subscription
        else:
            raise PermissionDenied()

        return ctx
