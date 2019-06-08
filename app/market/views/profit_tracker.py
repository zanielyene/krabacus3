from django.views.generic import TemplateView, FormView, View
from django.http import JsonResponse
from django.core.cache import cache
from django.views.generic.detail import SingleObjectMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from market.models import TradingRoute, MarketPriceDAO, PlayerTransaction, MarketOrder, TransactionLinkage
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


class ProfitData(JSONResponseMixin, TemplateView):

    def render_to_response(self, context, **response_kwargs):
        return self.render_to_json_response(context, **response_kwargs)

    @staticmethod
    def calculate_table_data(route):
        thirty_ago = timezone.now() - timedelta(days=30)

        links = TransactionLinkage.objects.filter(route=route, date_linked__gte=thirty_ago)

        object_types = links.values_list('source_transaction__object_type', flat=True).distinct()

        object_type_lookup = {}

        @dataclass
        class ObjectProfitData:
            obj_type: ObjectType
            qty_sold: int
            qty_purchased: int
            qty_on_market: int
            total_profit: float

        for o in object_types:
            object_type_lookup[o] = ObjectProfitData(ObjectType.get_object(o),0,0,0,0.0)

        for link in links:
            obj_type = link.source_transaction.object_type
            data = object_type_lookup[obj_type.ccp_id]
            data.qty_sold += link.quantity_linked
            data.qty_purchased += link.quantity_linked

            cogs = route.calculate_cogs_from_linkage(link)
            #print("cogs from sale of {} is {} ea {} units with sell price of {}".format(obj_type, cogs/link.quantity_linked, link.quantity_linked, link.destination_transaction.unit_price))
            revenue = link.quantity_linked * link.destination_transaction.unit_price
            profit = revenue - cogs
            data.total_profit += profit

        # convert to the format we send to client
        ret = []
        for data in object_type_lookup.values():
            ret.append([
                data.obj_type.name,
                #data.qty_purchased,
                data.qty_sold,
                #data.qty_on_market,
                data.qty_sold / 30.0,
                data.total_profit / data.qty_sold,
                data.total_profit
            ])
        return ret


    @staticmethod
    def get_table_data(route, data_length, data_skip, sort_column, sort_direction):
        if route is None:
            # demo mode
            items = cache.get("profit_tracker_demo_data")
            if not items:
                f = open(settings.DEMO_FILE_LOCATION +  "profit_tracker_demo_data.json", "r")
                items = json.loads(f.read())
                f.close()
                cache.set("profit_tracker_demo_data", items, 86400)
        else:

            items = cache.get("cached_profit_table_{}".format(route.pk))
            if not items:
                items = ProfitData.calculate_table_data(route)
                timeout = 5 if settings.DEBUG else 300
                cache.set("cached_profit_table_{}".format(route.pk), items, timeout=timeout)


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

        ctx = super(ProfitData, self).get_context_data(**kwargs)

        data_length = int(self.request.GET['length'])
        data_skip = int(self.request.GET['start'])
        sort_column = int(self.request.GET['order[0][column]'])
        sort_direction = self.request.GET['order[0][dir]']

        data, total_count = ProfitData.get_table_data(
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


profit_fields = [
            "Item Type Sold",
            #"Quantity Purchased",
            "Quantity Sold",
            #"Quantity on Market",
            "Average Sell Rate",
            "Average Unit Profit",
            "Total Profit",
            #"Item Breakeven Price",
        ]
