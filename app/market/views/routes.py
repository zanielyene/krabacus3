from django.views.generic import TemplateView, FormView, View
from django.http import JsonResponse, HttpResponseRedirect
from django.core.cache import cache
from django.template.response import TemplateResponse
from django.views.generic.detail import SingleObjectMixin
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from market.forms import TradingRouteForm

from market.models import ItemGroup, StructureMarketScanLog, MarketHistoryScanLog, PlayerTransactionScanLog, PlayerOrderScanLog, TradingRoute
from market.tasks import update_player_orders, update_region_market_history, update_player_transactions, update_structure_orders
from eve_api.models import ObjectType
from market.forms import EditRouteForm

import logging
from enum import Enum
from dataclasses import dataclass
from .transactions import transaction_fields
from .eye_of_krab import table_fields
from .orders import order_fields
from .profit_tracker import profit_fields
from .shopping_list import shoppinglist_fields
from market.views.route_config import EditRouteView

from braces.views import LoginRequiredMixin

logger=logging.getLogger(__name__)


class SingleRouteView(LoginRequiredMixin, SingleObjectMixin, TemplateView):
    model = TradingRoute
    template_name = 'market/route_table.html'

    def get_context_data(self, **kwargs):
        self.object = self.get_object()
        ctx = super(SingleRouteView, self).get_context_data(**kwargs)

        ctx["route"] = self.object
        ctx["eye_of_krab_fields"] = table_fields
        ctx["transaction_fields"] = transaction_fields
        ctx["order_fields"] = order_fields
        ctx["profit_fields"] = profit_fields
        ctx["shoppinglist_fields"] = shoppinglist_fields

        if self.request.user == self.object.creator:
            self.object.last_viewed = timezone.now()
            self.object.save()

        dest_market_data_scan = StructureMarketScanLog.get_most_recent_completed_scan(self.object.destination_structure.pk)
        source_market_data_scan = StructureMarketScanLog.get_most_recent_completed_scan(self.object.source_structure.pk)
        market_history_scan = MarketHistoryScanLog.get_most_recent_completed_scan(self.object.destination_structure.location.region.pk)
        source_char_transactions_scan = PlayerTransactionScanLog.get_most_recent_completed_scan(self.object.source_character.pk)
        dest_char_transactions_scan = PlayerTransactionScanLog.get_most_recent_completed_scan(self.object.destination_character.pk)
        dest_char_orders_scan = PlayerOrderScanLog.get_most_recent_completed_scan(self.object.destination_character.pk)

        if dest_market_data_scan is None:
            messages.warning(
                self.request,
                "Currently scanning {} for the first time. Data may be inaccurate until completed.".format(self.object.destination_structure.name)
            )
        if source_market_data_scan is None:
            messages.warning(
                self.request,
                "Currently scanning {} for the first time. Data may be inaccurate until completed.".format(self.object.source_structure.name)
            )
        if market_history_scan is None:
            messages.warning(
                self.request,
                "Currently scanning {}'s market history for the first time. Data may be inaccurate until completed.".format(self.object.destination_structure.location.region.name)
            )
        if source_char_transactions_scan is None:
            messages.warning(
                self.request,
                "Currently scanning {}'s transaction history for the first time. Data may be inaccurate until completed.".format(self.object.source_character.name)
            )
        if dest_char_transactions_scan is None:
            messages.warning(
                self.request,
                "Currently scanning {}'s transaction history for the first time. Data may be inaccurate until completed.".format(self.object.destination_character.name)
            )
        if dest_char_orders_scan is None:
            messages.warning(
                self.request,
                "Currently scanning {}'s market orders for the first time. Data may be inaccurate until completed.".format(self.object.destination_character.name)
            )

        ctx["source_char_transactions_scan"] = source_char_transactions_scan
        ctx["dest_char_transactions_scan"] = dest_char_transactions_scan
        ctx["dest_char_orders_scan"] = dest_char_orders_scan
        ctx["source_market_data_scan"] = source_market_data_scan
        ctx["dest_market_data_scan"] = dest_market_data_scan
        ctx["market_history_scan"] = market_history_scan
        ctx["edit_route_form"] = EditRouteView.get_populated_form(self.object)

        return ctx



class SingleRouteDemoView(TemplateView):
    template_name = 'market/demo/route_table.html'

    def get_context_data(self, **kwargs):
        ctx = super(SingleRouteDemoView, self).get_context_data(**kwargs)

        demo_route = {
            "pk": "00000000-0000-0000-0000-000000000000",
            "source_character":"SOURCE CHARACTER",
            "destination_character": "DESTINATION CHARACTER",
            "source_structure": "SOURCE STRUCTURE (usually jita)",
            "destination_structure": "DESTINATION STRUCTURE"
        }
        ctx["route"] = demo_route
        ctx["eye_of_krab_fields"] = table_fields
        ctx["transaction_fields"] = transaction_fields
        ctx["order_fields"] = order_fields
        ctx["profit_fields"] = profit_fields
        ctx["shoppinglist_fields"] = shoppinglist_fields


        ctx["edit_route_form"] = EditRouteForm(initial={
            'route': None,
            'price_per_m3':1500,
            'collateral_pct':1,
            'sales_tax': 3,
            'broker_fee': 3,
            'colorblind': False,
        })

        return ctx


class RoutesView(LoginRequiredMixin, TemplateView):
    template_name = 'market/routes_index.html'

    def get_context_data(self, **kwargs):
        ctx = super(RoutesView, self).get_context_data(**kwargs)

        routes = TradingRoute.objects.filter(creator=self.request.user)
        ctx["routes"] = routes
        return ctx


class CreateRouteView(LoginRequiredMixin, FormView):
    template_name = 'market/create_route.html'
    form_class = TradingRouteForm
    success_url = reverse_lazy("market:routes")


    def _trigger_scans_from_route_creation(self, route):
        scanning_happening = False
        oldest_allowable_player_scan = timezone.now() - timedelta(hours=2)
        last_scan = PlayerOrderScanLog.get_most_recent_completed_scan(route.destination_character.pk)
        if not last_scan or last_scan.scan_complete < oldest_allowable_player_scan:
            logger.info("Launching first-time player order scan for dst char {}".format(route.destination_character.pk))
            scanning_happening = True
            update_player_orders(route.destination_character.pk)

        last_scan = PlayerTransactionScanLog.get_most_recent_completed_scan(route.destination_character.pk)
        if not last_scan or last_scan.scan_complete < oldest_allowable_player_scan:
            logger.info("Launching first-time player transaction scan for dst char {}".format(route.destination_character.pk))
            scanning_happening = True
            update_player_transactions(route.destination_character.pk)

        last_scan = PlayerTransactionScanLog.get_most_recent_completed_scan(route.source_character.pk)
        if not last_scan or last_scan.scan_complete < oldest_allowable_player_scan:
            logger.info("Launching first-time player order scan for src char {}".format(route.source_character.pk))
            scanning_happening = True
            update_player_transactions(route.source_character.pk)

        oldest_allowable_history_scan = timezone.now() - timedelta(hours=30)
        last_scan = MarketHistoryScanLog.get_most_recent_completed_scan(route.destination_structure.location.region.pk)
        if not last_scan or last_scan.scan_complete < oldest_allowable_history_scan:
            logger.info("Launching first-time market history scan for {}".format(route.destination_structure.location.region.name))
            scanning_happening = True
            update_region_market_history(route.destination_structure.location.region.pk)

        oldest_allowable_market_scan = timezone.now() - timedelta(minutes=30)
        last_scan = StructureMarketScanLog.get_most_recent_completed_scan(route.destination_structure.pk)
        if not last_scan or last_scan.scan_complete < oldest_allowable_market_scan:
            logger.info("Launching first-time market orders scan for {}".format(route.destination_structure.name))
            scanning_happening = True
            update_structure_orders(route.destination_structure.pk)

        #if scanning_happening:
        #    messages.info(self.request, "Your route has been queued for a first-time scan. It may take a bit before it's fully ready to use.")
        return

    def form_valid(self, form):
        if form.is_valid():
            source_character = form.cleaned_data["source_character"]
            source_structure = form.cleaned_data["source_structure"]
            destination_character = form.cleaned_data["destination_character"]
            destination_structure = form.cleaned_data["destination_structure"]

            price_per_m3 = form.cleaned_data["price_per_m3"]
            collateral_pct = form.cleaned_data["collateral_pct"]
            sales_tax = form.cleaned_data["sales_tax"]
            broker_fee = form.cleaned_data["broker_fee"]
            #item_groups = form.cleaned_data["item_groups"]

            # todo: verify characters belong to this guy
            # todo: verify this guy has access to those structures

            route = TradingRoute(
                creator = self.request.user,
                source_structure = source_structure,
                source_character = source_character,
                destination_character = destination_character,
                destination_structure = destination_structure,
                cost_per_m3 = price_per_m3,
                pct_collateral = collateral_pct,
                sales_tax = sales_tax,
                broker_fee = broker_fee
            )
            route.save()
            all_item_groups = ItemGroup.objects.all()
            route.item_groups.set(all_item_groups)

            messages.info(self.request, "Route created successfully.")
            self._trigger_scans_from_route_creation(route)
            # change success redirect to the route page
            self.success_url = reverse(viewname='market:route-view', args=[str(route.pk)])
            return super(CreateRouteView, self).form_valid(form)


