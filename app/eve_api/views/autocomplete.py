from dal import autocomplete

from eve_api.models import EVEPlayerCorporation, EVEPlayerCharacter, Structure, ObjectType, EsiKey
from eve_api.tasks.esi_structure_search import structure_search
from django import http
from django.db.models.functions import Length
import logging

logger = logging.getLogger(__name__)


class EVEPlayerCorporationAutcomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # only admin should ever be using this autocomplete widget
        if self.request.user and self.request.user.is_superuser:
            qs = EVEPlayerCorporation.objects.all().order_by('name')
            if self.q:
                qs = qs.filter(name__istartswith=self.q)

            return qs
        else:
            return EVEPlayerCorporation.objects.none()


class EVEPlayerCharacterAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated:
            chars = EVEPlayerCharacter.objects.filter(key__owner=self.request.user, key__use_key=True)

            chars = chars.order_by('name')
            if self.q:
                chars = chars.filter(name__icontains=self.q)

            return chars
        else:
            return EVEPlayerCharacter.objects.none()


class EVEStructureAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user:
            character_id = self.forwarded.get('character', None)
            if character_id == "":
                return Structure.objects.none()
            qs = Structure.objects.none()
            if self.q and EsiKey.does_user_have_access(self.request.user,character_id):
                # use esi structure search. do not use name__icontains because our structure names may be out of date.
                # this also handles any problems with showing people the wrong structures.
                structure_ids = structure_search(character_id, self.q)
                qs = Structure.objects.filter(pk__in=structure_ids).order_by('name')
            return qs
        else:
            return Structure.objects.none()


class EVEObjectTypeAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated:
            qs = ObjectType.objects.filter(market_group__isnull=False, published=True).order_by(Length('name').asc())
            if self.q:
                qs = qs.filter(name__istartswith=self.q)

            return qs
        else:
            return ObjectType.objects.none()
