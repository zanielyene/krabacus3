from django.views.generic import TemplateView, FormView, View
from django.http import JsonResponse, HttpResponseRedirect, HttpResponseForbidden
from django.core.exceptions import PermissionDenied
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

from braces.views import LoginRequiredMixin


class DeleteRouteView(LoginRequiredMixin,SingleObjectMixin, View):
    template_name = 'market/delete_route.html'
    model = TradingRoute

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.creator == self.request.user:
            return HttpResponseForbidden()
        return TemplateResponse(request, 'market/delete_route.html', {"route":self.object})

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        if not obj.creator == self.request.user:
            return HttpResponseForbidden()
        route_name = str(obj)
        obj.delete()
        messages.info(request, "{} route deleted".format(route_name))
        return HttpResponseRedirect(reverse_lazy("market:routes"))


class EditRouteView(LoginRequiredMixin, FormView):
    template_name = 'market/create_route.html'
    form_class = EditRouteForm
    success_url = reverse_lazy("market:routes")

    @staticmethod
    def get_populated_form(route):
        return EditRouteForm(initial={
            'route': route,
            'price_per_m3':route.cost_per_m3,
            'collateral_pct':route.pct_collateral,
            'sales_tax': route.sales_tax,
            'broker_fee': route.broker_fee,
            'colorblind': route.colorblind,
        })

    def form_valid(self, form):
        if form.is_valid():
            price_per_m3 = form.cleaned_data["price_per_m3"]
            collateral_pct = form.cleaned_data["collateral_pct"]
            sales_tax = form.cleaned_data["sales_tax"]
            broker_fee = form.cleaned_data["broker_fee"]
            colorblind = form.cleaned_data["colorblind"]


            route = form.cleaned_data["route"]
            if route.creator != self.request.user:
                raise PermissionDenied()

            route.cost_per_m3 = price_per_m3
            route.pct_collateral = collateral_pct
            route.sales_tax = sales_tax
            route.broker_fee = broker_fee
            route.colorblind = colorblind

            route.save()
            messages.info(self.request, "Route details updated.")
            self.success_url = reverse(viewname='market:route-view', args=[str(route.pk)])

            return super(EditRouteView, self).form_valid(form)