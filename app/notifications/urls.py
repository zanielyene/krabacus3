from django.conf.urls import url
from django.views.generic import RedirectView

from .views import UpdatesView

app_name = 'notifications'
urlpatterns = [
    url(r'^$', UpdatesView.as_view(), name='updates'),
]


