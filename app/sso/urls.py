from django.conf.urls import url
from django.views.generic import RedirectView

from sso import views, auth_views
from sso.autocomplete import UserAutcomplete
from market.views import CreateRouteView

app_name = 'sso'
urlpatterns = [
    url(r'^$', views.ProfileView.as_view(), name='home'),

    # overwrites django default
    url(r'^login/$', auth_views.EsiLoginAsAuthenticationView.as_view(), name="esi-login"),
    url(r'^add_key/$', auth_views.EsiLoginToAddKeyView.as_view(), name="esi-add-key"),


    url(r'^o2/callback/$', auth_views.EsiLoginCallbackView.as_view(), name="esi-login-callback"),
    url(r'^user_autocomplete/$', UserAutcomplete.as_view(), name="user-autocomplete"),
    url(r'^profile/$', views.ProfileView.as_view(), name='profile'),
    url(r'^profilefst/$', CreateRouteView.as_view(), name='profilefirst'),
    url(r'^analytics/$', views.AnalyticsView.as_view(), name='analytics'),
    url(r'^account/$', views.AccountView.as_view(), name='account'),
    url(r'^subscribe/$', views.AccountView.as_view(), name='subscribe'),
    url(r'^key_add_success/$', auth_views.KeyAddSuccessView.as_view(), name='key-add-success'),
    #url(r'roles', views.sso_role_view, name="sso-get-roles"),

]


