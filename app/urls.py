from django.conf.urls import url, include
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.conf import settings
from django.contrib.auth import views as auth_views
#import registration.backends.default.views
from django.contrib.auth import views as auth_views

from utils import installed
#from sso.forms import RegistrationFormUniqueEmailBlocked
#from sso.custom_authorization_view import SpecialAuthorizationView

#from oauth2_provider import views as oauth_views

admin.autodiscover()
from django.conf import settings
from django.conf.urls import include, url
import logging


urlpatterns = [
    #url(r'^register/$', registration.backends.default.views.RegistrationView.as_view(form_class=RegistrationFormUniqueEmailBlocked)),

    url('', include('sso.urls')),
    url('', include('django.contrib.auth.urls')),
    url(r'^eve/', include('eve_api.urls')),
    url(r'^market/', include('market.urls')),
    url(r'^updates/', include('notifications.urls')),
    url('logout/', auth_views.LogoutView.as_view(), name='logout'),
    #url(r'^o2/authorize/$', SpecialAuthorizationView.as_view(), name="authorize"),

    #url(r'^o2/token/$', oauth_views.TokenView.as_view(), name="token"),
    #url(r'^o2/revoke_token/$', oauth_views.RevokeTokenView.as_view(), name="revoke-token"),

]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns

if installed('sentry'):
    urlpatterns += [
        url(r'^sentry/', include('sentry.web.urls')),
    ]

if installed('nexus'):
    import nexus
    nexus.autodiscover()

    urlpatterns += [
        url(r'^admin/', include('nexus.site.urls')),
    ]
else:
    urlpatterns += [
        url(r'^admin/', admin.site.urls),
    ]


if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()


def handler500(request):
    """
    500 error handler which includes ``request`` in the context.

    Templates: `500.html`
    Context: None
    """
    from django.template import Context, loader
    from django.http import HttpResponseServerError

    t = loader.get_template('500.html')
    return HttpResponseServerError(t.render({'request': request}))
    
