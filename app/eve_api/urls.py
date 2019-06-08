from django.conf.urls import url

from eve_api import views
import eve_api.views.autocomplete as autocomplete


app_name = 'eve_api'
urlpatterns = [
    url(r'^structure_autocomplete/$', autocomplete.EVEStructureAutocomplete.as_view(),name='eveapi-structure-autocomplete'),
    url(r'^character_autocomplete/$',  autocomplete.EVEPlayerCharacterAutocomplete.as_view(),name='eveapi-character-autocomplete'),
    url(r'^object_type_autocomplete/$',  autocomplete.EVEObjectTypeAutocomplete.as_view(),name='eveapi-objecttype-autocomplete'),
]
