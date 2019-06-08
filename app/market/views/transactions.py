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

import logging
import json
from enum import Enum
from dataclasses import dataclass

from braces.views import LoginRequiredMixin

logger=logging.getLogger(__name__)


class JSONResponseMixin:
    def render_to_json_response(self, context, **response_kwargs):
        return JsonResponse(
            self.get_data(context),
            **response_kwargs
        )

    def get_data(self, context):
        return context["payload"]


class TransactionsData(SingleObjectMixin, JSONResponseMixin, TemplateView):
    model = TradingRoute

    def render_to_response(self, context, **response_kwargs):
        return self.render_to_json_response(context, **response_kwargs)


    @staticmethod
    def calculate_table_data(route):
        dest_char = route.destination_character
        dest_structure = route.destination_structure
        transactions = PlayerTransaction.objects.filter(
            character = dest_char,
            location = dest_structure,
            is_buy = False,
        ).order_by('timestamp')

        player_orders = MarketOrder.objects.filter(
            character=dest_char,
            location=dest_structure,
            is_buy_order=False,
            order_active=True
        )
        obj_ids = [t.object_type.pk for t in transactions]
        obj_prices = MarketPriceDAO.get_src_lowest_sell_multi(obj_ids, route)
        data = []
        zipped = zip(transactions, obj_prices)
        for t, obj_price in zipped:
            source_data = t.get_source_value(t.quantity, route)

            any_orders_on_market = player_orders.filter(object_type=t.object_type).exists()

            data.append(
                [
                    t.timestamp,
                    t.object_type.name,
                    t.quantity,
                    t.unit_price,
                    source_data.unit_price if source_data else None,
                    (t.unit_price - source_data.unit_price) if source_data else None,
                    t.unit_price * t.quantity,
                    source_data.total_price if source_data else None,
                    (t.unit_price * t.quantity - source_data.total_price) if source_data else None,
                    any_orders_on_market,
                    obj_price,
                    t.object_type.pk,
                ]
            )
        return data

    @staticmethod
    def get_table_data(route, data_length, data_skip, sort_column, sort_direction):
        if route is None:
            # demo mode
            items = cache.get("transactions_demo_data")
            if not items:
                f = open(settings.DEMO_FILE_LOCATION +  "transactions_demo_data.json", "r")
                items = json.loads(f.read())
                f.close()
                cache.set("transactions_demo_data", items, 86400)
        else:
            items = cache.get("cached_transactions_table_{}".format(route.pk))
            if not items:
                items = TransactionsData.calculate_table_data(route)
                timeout = 60 if settings.DEBUG else 600
                cache.set("cached_transactions_table_{}".format(route.pk), items, timeout=timeout)

        sort_direction_bool = False if sort_direction == "asc" else True
        total_item_count = len(items)

        def sort_key(i):
            if i[sort_column] is None:
                return 0.0
            if type(i[sort_column]) is str:
                return i[sort_column].lower()
            return i[sort_column]

        sorted_items = sorted(items, key=sort_key, reverse=sort_direction_bool)
        sliced_items = sorted_items[data_skip:data_length+data_skip]

        # append shopping list quantities
        # we use semi-hard coded object_id column
        obj_id_col = transaction_fields.index("Object ID")
        shopping_lookup = ShoppingListItem.get_route_shopping_lookup(route)
        for row in sliced_items:
            obj_id = row[obj_id_col]
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

        ctx = super(TransactionsData, self).get_context_data(**kwargs)

        data_length = int(self.request.GET['length'])
        data_skip = int(self.request.GET['start'])
        sort_column = int(self.request.GET['order[0][column]'])
        sort_direction = self.request.GET['order[0][dir]']

        data, total_count = TransactionsData.get_table_data(
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

transaction_fields = [
            "Timestamp",
            "Item Type",
            "Quantity Sold",
            "Unit Sell Price",
            "Unit Purchase Price",
            "Unit Profit",
            "Total Sell Price",
            "Total Purchase Price",
            "Total Profit",
            "Any Orders on Market",
            "Source Sell Price",
            "Object ID",
            "Shopping List Qty",
            # "Turnover Time"
        ]

class TransactionsView(LoginRequiredMixin, SingleObjectMixin, TemplateView):

    model = TradingRoute

    template_name = 'market/transactions_wrapper.html'

    def get_context_data(self, **kwargs):
        self.object = self.get_object()
        ctx = super(TransactionsView, self).get_context_data(**kwargs)


        data, total_count  = TransactionsData.get_table_data(self.object, 50, 0, 0, "desc")
        ctx["items"] = data
        ctx["transaction_fields"] = transaction_fields
        ctx["route"] = self.object
        ctx["num_entries"] = total_count
        return ctx
