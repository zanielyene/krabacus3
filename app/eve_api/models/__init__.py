"""
By importing all of these sub-modules, the models package is transparently
accessible by the rest of the project. This makes it act just as if it were
one monolithic models.py.
"""

from django.db import models
import huey
from conf.huey_queues import general_queue



from .corporation import *
from .alliance import *
from .esi_models import *
from .character import *
from .type_category import TypeCategory
from .type_group import TypeGroup
from .market_group import MarketGroup
from .object_type import ObjectType
from .region import Region
from .constellation import Constellation
from .structure import Structure
from .location import Location
from .system import System
from .ccp_id_resolver import CcpIdTypeResolver
from .faction import Faction
from .esi_key import EsiKey, CharacterAssociation


@general_queue.task()
def bootstrap_esi_database():
    from .market_group import import_all_market_groups
    from .type_category import import_all_type_categories
    from .type_group import import_all_type_groups
    from .object_type import import_all_item_types
    from .region import import_universe_regions
    from .constellation import import_universe_constellations
    from .system import import_universe_systems
    from .faction import import_universe_factions
    from market.tasks import initialize_item_groups

    pipeline = (import_all_market_groups.s()
                .then(import_all_type_categories)
                .then(import_all_type_groups)
                .then(import_all_item_types)
                .then(import_universe_regions)
                .then(import_universe_constellations)
                .then(import_universe_systems)
                .then(import_universe_factions)
                .then(initialize_item_groups))

    general_queue.enqueue(pipeline)
