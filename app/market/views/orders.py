from django.views.generic import TemplateView, FormView, View
from django.http import JsonResponse
from django.core.cache import cache
from django.views.generic.detail import SingleObjectMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.conf import settings

from market.models import TradingRoute, MarketPriceDAO, PlayerTransaction, MarketOrder, ShoppingListItem
from market.models.market_price_dao import MarketDataType
from market.forms import TradingRouteForm

from eve_api.models import ObjectType

import json
import logging
from enum import Enum
from dataclasses import dataclass

from braces.views import LoginRequiredMixin

logger = logging.getLogger(__name__)


class JSONResponseMixin:
    def render_to_json_response(self, context, **response_kwargs):
        return JsonResponse(
            self.get_data(context),
            **response_kwargs
        )

    def get_data(self, context):
        return context["payload"]


class OrdersData(JSONResponseMixin, TemplateView):

    def render_to_response(self, context, **response_kwargs):
        return self.render_to_json_response(context, **response_kwargs)

    @staticmethod
    def calculate_table_data(route):
        dest_char = route.destination_character
        dest_structure = route.destination_structure
        valid_items = route.item_ids
        orders = MarketOrder.objects.filter(
            character=dest_char,
            object_type_id__in=valid_items,
            is_buy_order=False,
            location=dest_structure,
            order_active=True
        ).order_by('object_type__name')

        data = []
        order_type_ids = [o.object_type_id for o in orders]
        lowest_sell_prices = MarketPriceDAO.get_dest_lowest_sell_multi(order_type_ids, route)
        lowest_order_ids = MarketPriceDAO.get_dest_lowest_order_multi(order_type_ids, route)
        lowest_src_sell_price = MarketPriceDAO.get_src_lowest_sell_multi(order_type_ids, route)
        zipped_orders = zip(orders, lowest_sell_prices, lowest_order_ids, lowest_src_sell_price)

        for order, lowest_sell_price, lowest_orders, lowest_src_sell in zipped_orders:
            q_remain = order.volume_remain
            q_total = order.volume_total

            if len(lowest_orders) > 1:
                is_lowest = False
            elif order.ccp_id in lowest_orders:
                is_lowest = True
            else:
                is_lowest = False

            # get breakeven
            breakeven_for_order = route.estimate_cogs(order.object_type, q_remain, order.price)
            unit_breakeven = breakeven_for_order / q_remain if breakeven_for_order else None
            data.append(
                [
                    order.object_type.name,
                    not is_lowest,
                    "N/A" if is_lowest else round(lowest_sell_price - 0.01,2),
                    order.price,
                    0 if is_lowest else ((order.price - unit_breakeven) - (lowest_sell_price -unit_breakeven)) / (order.price-unit_breakeven) * 100 if unit_breakeven else None,
                    unit_breakeven,
                    q_remain,
                    q_total,
                    q_remain / q_total * 100,
                    order.object_type.pk,
                    lowest_src_sell,
                ]
            )
        return data

    @staticmethod
    def get_table_data(route, data_length, data_skip, sort_column, sort_direction):
        if route is None:
            # demo mode
            items = cache.get("orders_demo_data")
            if not items:
                f = open(settings.DEMO_FILE_LOCATION + "orders_demo_data.json", "r")
                items = json.loads(f.read())
                f.close()
                cache.set("orders_demo_data", items, 86400)
        else:
            items = cache.get("acached_orders_table_{}".format(route.pk))
            if not items:
                items = OrdersData.calculate_table_data(route)
                timeout = 5 if settings.DEBUG else 5
                cache.set("acached_orders_table_{}".format(route.pk), items, timeout=timeout)


        sort_direction_bool = False if sort_direction == "asc" else True
        total_item_count = len(items)

        def sort_key(i):
            if i[sort_column] is None or i[sort_column] == "N/A":
                return 0.0
            if type(i[sort_column]) is str:
                return i[sort_column].lower()
            return i[sort_column]

        sorted_items = sorted(items, key=sort_key, reverse=sort_direction_bool)
        sliced_items = sorted_items[data_skip:data_length+data_skip]

        shopping_lookup = ShoppingListItem.get_route_shopping_lookup(route)
        for row in sliced_items:
            # HARD CODED OBJECT ID COLUMN
            obj_id = row[9]
            val = shopping_lookup[obj_id].quantity if obj_id in shopping_lookup else 0
            row.append(val)

        return sliced_items, total_item_count

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

        ctx = super(OrdersData, self).get_context_data(**kwargs)

        data_length = int(self.request.GET['length'])
        data_skip = int(self.request.GET['start'])
        sort_column = int(self.request.GET['order[0][column]'])
        sort_direction = self.request.GET['order[0][dir]']

        data, total_count = OrdersData.get_table_data(
            self.object,
            data_length,
            data_skip,
            sort_column,
            sort_direction
        )
        draw_index = int(self.request.GET["draw"][0])

        ctx["payload"] = {
            "draw":draw_index,
            "recordsTotal":total_count,
            "recordsFiltered":total_count,
            "data": data
        }
        return ctx


order_fields = [
            "Item Type",
            "Is Being Undercut",
            "New Price",
            "Order Price",
            "Undercut Profit Impact",
            "Breakeven Price",
            "Volume Remain",
            "Volume Posted",
            "Proportion Remain",
            "object_id",
            "source sell price",
            "shopping_qty",


            #"Item Breakeven Price",
        ]
