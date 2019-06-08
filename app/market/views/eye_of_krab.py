from django.views.generic import TemplateView, FormView, View
from django.http import JsonResponse
from django.core.cache import cache
from django.views.generic.detail import SingleObjectMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.conf import settings

import json

from market.models import TradingRoute, MarketPriceDAO, ShoppingListItem
from market.models.market_price_dao import MarketDataType

from eve_api.models import ObjectType

import logging
from dataclasses import dataclass

from braces.views import LoginRequiredMixin

logger=logging.getLogger(__name__)




@dataclass
class TableField:
    field_type: MarketDataType
    name: str
    help_text: str

@dataclass
class TableEntry:
    item_type: ObjectType
    fields: list


table_fields = [
    TableField(
        MarketDataType.item_name,
        "Item",
        "The item's name"
    ),
    TableField(
        MarketDataType.dest_volume_posted,
        "Dest Volume Posted",
        "The amount of the item posted in the destination station."
    ),
    TableField(
        MarketDataType.dest_velocity,
        "Dest Region Sell Rate",
        "The average amount of item sold each day in destination REGION (sorry hiseccers, you're screwed. If there's only one market hub in your entire region, then this number is a pretty good representation of how fast items sell in that hub.). Calculated using moving average over past 10 days."
    ),
    TableField(
        MarketDataType.dest_depletion_estimate,
        "Depletion Est.",
        "Estimated number of days until the market in the destination structure is depleted, assuming nobody imports more of the item. Equal to (Dest Volume Posted)/(Dest Velocity)."
    ),
    TableField(
        MarketDataType.dest_lowest_sell,
        "Destination Sell",
        "The lowest sell price of the item in the destination structure."
    ),
    TableField(
        MarketDataType.src_lowest_sell,
        "Source Sell",
        "The lowest sell price of the item in the source structure."
    ),
    TableField(
        MarketDataType.freight_cost_total,
        "Freight Cost",
        "The freight cost of shipping the object to the destination structure."
    ),
    TableField(
        MarketDataType.listing_cost,
        "Listing Cost",
        "The cost of creating the order."
    ),
    TableField(
        MarketDataType.cogs,
        "TCIL",
        "Total Cost to Import and List. This is equal to Source Sell Price + Freight Cost + Listing Cost"
    ),
    TableField(
        MarketDataType.unit_profit,
        "Unit Profit",
        "The amount you would make by buying this item in the source station, importing it, then selling it at current sell prices. Equal to (Dest Sell Price)-(TCIL)"
    ),
    TableField(
        MarketDataType.capital_efficiency,
        "Return on Investment",
        "AKA Profit Margin, AKA Capital Efficiency, This number helps evaluate how efficient it is to trade this item on this route. A return on investment of 200% means that for every 100 ISK you invest importing this item, you should make 200 ISK profit."
    ),
    TableField(
        MarketDataType.projected_daily_profit,
        "Max Potential Profit",
        "The amount you would make every day by importing this item and capturing all of the potential profit in the ENTIRE REGION. Equal to Dest Velocity * Unit Profit. This number does NOT take market competition into consideration!"
    ),
    TableField(
        MarketDataType.item_id,
        "Item ID",
        ""
    ),
    TableField(
        MarketDataType.dest_max_sell_past_30,
        "Dest max sell past 30d",
        ""
    ),
]


def resolve_fields(route, fields, object_type):
    ret_fields = []
    func_lu = MarketPriceDAO.get_bindings()

    for field in fields:
        value = func_lu[field.field_type](object_type, route)
        ret_fields.append(value)

    return TableEntry(object_type, ret_fields)


def resolve_columns(route, fields, object_types):
    ret = []

    func_lu = MarketPriceDAO.get_multi_bindings()
    object_type_ids = [o.pk for o in object_types]
    for field in fields:
        values = func_lu[field.field_type](object_type_ids, route)
        ret.append(values)

    return [list(x) for x in zip(*ret)]


class JSONResponseMixin:
    def render_to_json_response(self, context, **response_kwargs):
        return JsonResponse(
            self.get_data(context),
            **response_kwargs
        )

    def get_data(self, context):
        return context["payload"]


class EyeofKrabData(JSONResponseMixin, TemplateView):

    def render_to_response(self, context, **response_kwargs):
        return self.render_to_json_response(context, **response_kwargs)

    @staticmethod
    def filter_table(search_term, filter_params, items):
        # build quick lookup for column indexes
        col_lu = [t.field_type for t in table_fields]

        if search_term is not None:
            search_filtered = []
            name_index = col_lu.index(MarketDataType.item_name)
            for i in items:
                if i[name_index].lower().startswith(search_term.lower()):
                    search_filtered.append(i)
            items = search_filtered

        # for each filter type, apply filter
        for coltype, param in filter_params.items():
            if not param["comparator"] or param["amount"] is None or param["amount"]=="":
                continue
            else:
                col_index = col_lu.index(coltype)

                # sort data before clipping
                def sort_key(i):
                    if i[col_index] is None:
                        return 0.0
                    if type(i[col_index]) is str:
                        return i[col_index].lower()
                    return i[col_index]

                items = sorted(items, key=sort_key)
                cmp_value = float(param["amount"])

                if param["comparator"] == "=":
                    items = [item for item in items if (item[col_index] if item[col_index] else 0) == cmp_value]
                elif param["comparator"] == "<":
                    items = [item for item in items if (item[col_index] if item[col_index] else 0) < cmp_value]
                elif param["comparator"] == ">":
                    items = [item for item in items if (item[col_index] if item[col_index] else 0) > cmp_value]
                elif param["comparator"] == ">=":
                    items = [item for item in items if (item[col_index] if item[col_index] else 0) >= cmp_value]
                elif param["comparator"] == "<=":
                    items = [item for item in items if (item[col_index] if item[col_index] else 0) <= cmp_value]
        return items

    @staticmethod
    def get_table_data(route, table_fields, data_length, data_skip, sort_column, sort_direction, filter_params, search_term):
        if route is None:
            # demo mode
            items = cache.get("cached_eye_demo_data")
            if not items:
                f = open(settings.DEMO_FILE_LOCATION + "eye_demo_data.json", "r")
                items = json.loads(f.read())
                f.close()
                cache.set("cached_eye_demo_data", items, 86400)
        else:
            items_list = route.items
            items = cache.get("cached_eye_of_krab_route_{}".format(route.pk))
            #i_str = str(items)
            #logger.info("data blob rows :{}".format(len(items)))
            #logger.info("data blob size: {}".format(len(i_str)))
            if not items:
                logger.info("Calculating eye of krab data")
                items = resolve_columns(route, table_fields, items_list)
                logger.info("Eye of krab data calculated")
                timeout = 1200 if settings.DEBUG else 1200
                cache.set("cached_eye_of_krab_route_{}".format(route.pk), items, timeout=timeout)
                logger.info("Cache set for eye of krab data")

        # apply filtering
        total_item_count = len(items)
        items = EyeofKrabData.filter_table(search_term, filter_params, items)

        sort_direction_bool = False if sort_direction == "asc" else True

        def sort_key(i):
            if i[sort_column] is None:
                return 0.0
            if type(i[sort_column]) is str:
                return i[sort_column].lower()
            return i[sort_column]

        sorted_items = sorted(items, key=sort_key, reverse=sort_direction_bool)

        sliced_items = sorted_items[data_skip:data_length+data_skip]

        # append shopping list quantities
        # assume object_id_col (hard code)
        object_id_col = 12
        shopping_lookup = ShoppingListItem.get_route_shopping_lookup(route)
        for row in sliced_items:
            obj_id = row[object_id_col]
            val = shopping_lookup[obj_id].quantity if obj_id in shopping_lookup else 0
            row.append(val)


        return sliced_items, total_item_count, len(items)

    def get_context_data(self, **kwargs):
        demo = False
        try:
            self.object = TradingRoute.objects.get(pk=kwargs["pk"])
            if not self.request.user.is_authenticated:
                raise PermissionError()
            if not self.request.user == self.object.creator and not self.request.user.is_superuser:
                raise PermissionError()

        except TradingRoute.DoesNotExist as e:
            if kwargs["pk"] == "00000000-0000-0000-0000-000000000000":
                demo = True
                self.object = None
            else:
                raise e
        ctx = super(EyeofKrabData, self).get_context_data(**kwargs)

        ctx["fields"] = table_fields

        data_length = int(self.request.GET['length'])
        data_skip = int(self.request.GET['start'])
        sort_column = int(self.request.GET['order[0][column]'])
        sort_direction = self.request.GET['order[0][dir]']

        search_term = self.request.GET.get("search_term")
        if search_term and search_term == "Enter an item name":
            search_term = None

        filter_params = {
            MarketDataType.dest_volume_posted: {
                "comparator":self.request.GET.get("filter_dest_volume_posted_comparator"),
                "amount": self.request.GET.get("filter_dest_volume_posted_value")
            },
            MarketDataType.dest_depletion_estimate: {
                "comparator": self.request.GET.get("filter_depletion_est_comparator"),
                "amount": self.request.GET.get("filter_depletion_est_value")
            },
            MarketDataType.dest_velocity: {
                "comparator": self.request.GET.get("filter_dest_sell_rate_comparator"),
                "amount": self.request.GET.get("filter_dest_sell_rate_value")
            },
            MarketDataType.unit_profit: {
                "comparator": self.request.GET.get("filter_unit_profit_comparator"),
                "amount": self.request.GET.get("filter_unit_profit_value")
            },
            MarketDataType.cogs: {
                "comparator": self.request.GET.get("filter_tcil_comparator"),
                "amount": self.request.GET.get("filter_tcil_value")
            },
            MarketDataType.capital_efficiency: {
                "comparator": self.request.GET.get("filter_cap_eff_comparator"),
                "amount": self.request.GET.get("filter_cap_eff_value")
            },
            MarketDataType.projected_daily_profit: {
                "comparator": self.request.GET.get("filter_max_profit_comparator"),
                "amount": self.request.GET.get("filter_max_profit_value")
            },
        }

        data, total_count, filtered_count = EyeofKrabData.get_table_data(
            self.object,
            table_fields,
            data_length,
            data_skip,
            sort_column,
            sort_direction,
            filter_params,
            search_term
        )
        draw_index = int(self.request.GET["draw"])

        ctx["payload"] = {
            "draw":draw_index,
            "recordsTotal":total_count,
            "recordsFiltered":filtered_count,
            "data": data,
        }

        return ctx


class EyeOfKrabView(LoginRequiredMixin, SingleObjectMixin, TemplateView):
    model = TradingRoute

    template_name = 'market/eye_of_the_krab_wrapper.html'

    def get_context_data(self, **kwargs):
        self.object = self.get_object()
        ctx = super(EyeOfKrabView, self).get_context_data(**kwargs)
        ctx["eye_of_krab_fields"] = table_fields

        ctx["route"] = self.object
        return ctx
