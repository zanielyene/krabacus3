from dal import autocomplete

from eve_api.models import EVEPlayerCorporation, EVEPlayerCharacter, Structure, ObjectType, EsiKey
from market.models import ItemGroup
from django.db.models import Q
from django.db.models.functions import Length

import logging

logger = logging.getLogger(__name__)


class ItemGroupAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated:
            # get item groups user has access to
            groups = ItemGroup.objects.filter(Q(creator__isnull=True) | Q(creator=self.request.user))

            groups = groups.order_by(Length('name').asc())

            if self.q:
                groups = groups.filter(name__icontains=self.q)

            return groups
        else:
            return ItemGroup.objects.none()

