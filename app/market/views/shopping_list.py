from django.views.generic import TemplateView, FormView, View
from django.http import JsonResponse, HttpResponseRedirect
from django.core.cache import cache
from django.template.response import TemplateResponse
from django.views.generic.detail import SingleObjectMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.conf import settings

from market.models import TradingRoute, MarketPriceDAO
from market.models.market_price_dao import MarketDataType

from market.models import ItemGroup
from market.models.shopping_list import ShoppingListItem
from eve_api.models import ObjectType

from django.http import HttpResponseForbidden, HttpResponseBadRequest
import logging
import json
from enum import Enum
from dataclasses import dataclass
from django.http import HttpResponse
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


class ShoppingListData(JSONResponseMixin, TemplateView):

    def render_to_response(self, context, **response_kwargs):
        return self.render_to_json_response(context, **response_kwargs)


    @staticmethod
    def calculate_table_data(route):

        shopping_items = ShoppingListItem.objects.filter(route=route).order_by('object_type__name')

        data = []

        # extract ids
        obj_ids = [item.object_type.pk for item in shopping_items]
        lowest_sell_price = MarketPriceDAO.get_src_lowest_sell_multi(obj_ids, route)
        items_and_prices = zip(shopping_items, lowest_sell_price)
        for item, lowest_sell in items_and_prices:
            data.append(
                [
                    item.object_type.name,
                    item.quantity,
                    lowest_sell if lowest_sell else 0,
                    lowest_sell * item.quantity if lowest_sell else 0,
                    item.object_type.pk
                ]
            )
        return data

    @staticmethod
    def get_table_data(route, data_length, data_skip, sort_column, sort_direction):
        if route is None:
            # demo mode
            items = cache.get("cached_shoppinglist_demo_data")
            if not items:
                f = open(settings.DEMO_FILE_LOCATION + "shopping_list_data.json", "r")
                items = json.loads(f.read())
                f.close()
                cache.set("cached_shoppinglist_demo_data", items, 86400)
        else:
            items = cache.get("cached_shopping_list_table_{}".format(route.pk))
            if not items:
                items = ShoppingListData.calculate_table_data(route)
                timeout = 1 if settings.DEBUG else 1
                cache.set("cached_shopping_list_table_{}".format(route.pk), items, timeout=timeout)

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

        ctx = super(ShoppingListData, self).get_context_data(**kwargs)

        data_length = int(self.request.GET['length'])
        data_skip = int(self.request.GET['start'])
        sort_column = int(self.request.GET['order[0][column]'])
        sort_direction = self.request.GET['order[0][dir]']

        data, total_count = ShoppingListData.get_table_data(
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


shoppinglist_fields = [
            "Item Type",
            "Quantity to purchase",
            "Unit Purchase Price",
            "Total Purchase Price",
            "object_id"
        ]

def shopping_list_clear_view(request, pk):
    if request.method == 'POST':
        if request.is_ajax():
            if request.user is None:
                return HttpResponseForbidden()

            if not TradingRoute.objects.filter(pk=pk).exists():
                return HttpResponseForbidden()

            route = TradingRoute.objects.get(pk=pk)
            if route.creator != request.user:
                return HttpResponseForbidden()

            list_items = ShoppingListItem.objects.filter(route=route)
            list_items.delete()
            return JsonResponse({"result":"ok"})
        else:
            return HttpResponseBadRequest()
    else:
        return HttpResponseBadRequest()



def shopping_list_edit_view(request, pk):
    if request.method == 'POST':
        if request.is_ajax():
            if request.user is None:
                return HttpResponseForbidden()

            if not TradingRoute.objects.filter(pk=pk).exists():
                return HttpResponseForbidden()

            route = TradingRoute.objects.get(pk=pk)
            if route.creator != request.user:
                return HttpResponseForbidden()

            object_id = request.POST.get('object_id')
            qty = request.POST.get('qty')

            if not object_id or qty is None:
                logger.error("object_id or qty is none")
                return HttpResponseBadRequest()

            exists = ObjectType.objects.filter(pk=object_id).exists()
            qty = int(qty)
            if not exists or qty < 0:
                logger.error("object type doesnt exist or quantity is less than 0")
                return HttpResponseBadRequest()

            # we're green to edit
            entry_exists = ShoppingListItem.objects.filter(object_type_id=object_id, route=route)
            if entry_exists:
                # remove or edit the existing entry
                entry = ShoppingListItem.objects.get(object_type_id=object_id, route=route)
                if qty == 0:
                    entry.delete()
                else:
                    entry.quantity = qty
                    entry.save()
            else:
                # create the entry if applicable
                if qty > 0:
                    entry = ShoppingListItem(
                        route=route,
                        object_type_id=object_id,
                        quantity=qty
                    )
                    entry.save()
            return JsonResponse({"result":"ok"})
        else:
            return HttpResponseBadRequest()
    else:
        return HttpResponseBadRequest()


