from django.conf.urls import url

from .models import *
from .tasks import *
from .views import *
from .autocomplete import ItemGroupAutocomplete


app_name = 'market'
urlpatterns = [
    url(r'^item_group_autocomplete/$', ItemGroupAutocomplete.as_view(), name='item-group-autocomplete'),
    url(r'^routes/create/$', CreateRouteView.as_view(), name='create-route'),
    url(r'^routes/eye/data/(?P<pk>[0-9a-f-]+)/$', EyeofKrabData.as_view(), name='eye-data'),
    #url(r'^routes/eye/(?P<pk>\d+)/$', EyeOfKrabView.as_view(), name='eye-view'),
    url(r'^routes/view/(?P<pk>[0-9a-f-]+)/$', SingleRouteView.as_view(), name='route-view'),
    url(r'^routes/edit/$', EditRouteView.as_view(), name='route-edit'),
    url(r'^routes/delete/(?P<pk>[0-9a-f-]+)/$', DeleteRouteView.as_view(), name='route-delete'),
    #url(r'^routes/transactions/(?P<pk>\d+)/$', TransactionsView.as_view(), name='transaction-view'),
    url(r'^routes/transactions/data/(?P<pk>[0-9a-f-]+)/$', TransactionsData.as_view(), name='transaction-data'),
    url(r'^routes/orders/data/(?P<pk>[0-9a-f-]+)/$', OrdersData.as_view(), name='order-data'),
    url(r'^routes/orders/profit/(?P<pk>[0-9a-f-]+)/$', ProfitData.as_view(), name='profit-data'),
    url(r'^routes/shopping/edit/(?P<pk>[0-9a-f-]+)/$', shopping_list_edit_view, name='edit-shopping-list'),
    url(r'^routes/shopping/clear/(?P<pk>[0-9a-f-]+)/$', shopping_list_clear_view, name='clear-shopping-list'),
    url(r'^routes/shopping/data/(?P<pk>[0-9a-f-]+)/$', ShoppingListData.as_view(), name='shopping-list-data'),

    url(r'^routes/view/demo/$', SingleRouteDemoView.as_view(), name='route-demo-view'),

    url(r'^routes/$', RoutesView.as_view(), name='routes'),
]
