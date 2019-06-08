from django import forms
from dal import autocomplete
from dal import forward
from django.forms.models import formset_factory
from django.forms import BaseFormSet
from django.http import QueryDict
from django.contrib.admin.widgets import FilteredSelectMultiple
from .models import *
from eve_api.models import Structure, EVEPlayerCharacter, ObjectType


class TradingRouteForm(forms.Form):
    source_character = forms.ModelChoiceField(
        EVEPlayerCharacter.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='eve_api:eveapi-character-autocomplete'
        )
    )

    source_structure = forms.ModelChoiceField(
        Structure.objects.all(),
        widget=autocomplete.ModelSelect2(
                url='eve_api:eveapi-structure-autocomplete',
                forward=[forward.Field('source_character', 'character')],
                attrs={
                    'data-minimum-input-length': 3,
                    'data-autocomplete-minimum-characters': 3,
                    'data-placeholder': "Structure Name (may take up to 10secs)"
                }
            )
    )

    price_per_m3 = forms.IntegerField(min_value=0, initial=1500)

    collateral_pct = forms.FloatField(min_value=0, max_value=1000, initial=1.00)
    sales_tax = forms.FloatField(min_value=0, max_value=100, initial=2.00)
    broker_fee = forms.FloatField(min_value=0, max_value=100, initial=3.00)

    destination_character = forms.ModelChoiceField(
        EVEPlayerCharacter.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='eve_api:eveapi-character-autocomplete'
        )
    )

    destination_structure = forms.ModelChoiceField(
        Structure.objects.all(),
        widget=autocomplete.ModelSelect2(
                url='eve_api:eveapi-structure-autocomplete',
                forward=[forward.Field('destination_character', 'character')],
                attrs={
                    'data-minimum-input-length': 3,
                    'data-autocomplete-minimum-characters': 3,
                    'data-placeholder': "Structure Name (may take up to 10secs)"
                }
            )
    )

    #item_groups = forms.ModelMultipleChoiceField(
    #    queryset=ItemGroup.objects.filter(creator__isnull=True),
    #    required=True,
    #    label="Item groups to import",
    #    widget=autocomplete.ModelSelect2Multiple(
    #            url='market:item-group-autocomplete',
    #            #Eforward=[forward.Field('source_character', 'character')],
    #            attrs={
    #                'data-minimum-input-length': 0,
    #                'data-autocomplete-minimum-characters': 0,
    #                'data-placeholder': ""
    #            }
    #        )
    #)



    class Meta:
        fields = ('__all__')


class EditShoppingListForm(forms.Form):
    object_type = forms.ModelChoiceField(ObjectType.objects.all())
    quantity = forms.IntegerField()

class EditRouteForm(forms.Form):
    route = forms.ModelChoiceField( queryset=TradingRoute.objects.all(), widget = forms.HiddenInput())
    price_per_m3 = forms.IntegerField(min_value=0)

    collateral_pct = forms.FloatField(min_value=0, max_value=1000)
    sales_tax = forms.FloatField(min_value=0, max_value=100)
    broker_fee = forms.FloatField(min_value=0, max_value=100)
    colorblind = forms.BooleanField(required=False)
