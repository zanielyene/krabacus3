from .structure_orders import *
from .structure_access import *
from .market_history import *
from .player_orders import *
from .player_transaction import *
from .player_assets import *


from conf.huey_queues import general_queue
from eve_api.models import TypeGroup, TypeCategory, ObjectType, MarketGroup
from market.models import ItemGroup


def import_group_recursive(group, parent_string=None):
    if not parent_string:
        parent_string = "zBuiltin: " + group.name
    else:
        parent_string += " -> {}".format(group.name)

    # check if we have any child groups. get their stuff first
    child_groups = MarketGroup.objects.filter(parent_id = group.pk)

    items = []
    for group in child_groups:
        child_items = import_group_recursive(group, parent_string)
        items.extend(child_items)

    # get this groups direct items
    direct_items = ObjectType.objects.filter(market_group=group)

    items.extend(direct_items)

    # now create the group
    if items:
        built_group = ItemGroup(
            name = parent_string
        )
        built_group.save()

        built_group.items.set(items)
    return items


@general_queue.task()
def initialize_item_groups():
    item_groups_to_commit = []

    # get market groups w/ no parent
    root_groups = MarketGroup.objects.filter(parent_id=None)

    for group in root_groups:
        child_groups = import_group_recursive(group)
        item_groups_to_commit.extend(child_groups)


    logger.info("all item market groups committed. end of init.")
