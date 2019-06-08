"""
Admin interface models. Automatically detected by admin.autodiscover().
"""
from django.contrib import admin, messages


from eve_api.models import *
from eve_api.tasks import hard_delete_esi_character_key
from django.forms import Textarea, TextInput, CheckboxInput
from django import forms

#def account_api_update(modeladmin, request, queryset):
#    for obj in queryset:
#        import_apikey.delay(api_key=obj.api_key, api_userid=obj.api_user_id)

#account_api_update.short_description = "Update account from the EVE API"


#def char_api_update(modeladmin, request, queryset):
#    for obj in queryset:
#        if obj.eveaccount_set.count():
#            import_eve_character.delay(obj.id, obj.eveaccount_set.all()[0].api_key, obj.eveaccount_set.all()[0].api_user_id)
#        else:
#            import_eve_character.delay(obj.id)

#char_api_update.short_description = "Update character information from the EVE API"


def delete_char_from_owners_account(modeladmin, request, queryset):
    if len(queryset) > 1:
        modeladmin.message_user(request, "Looks like you selected more than 1 character. I'm assuming you fucked something up so I'm throwing an exception.",level=messages.ERROR)
        return

    for char in queryset:
        hard_delete_esi_character_key(char.pk)
        char.owner_hash = None
        char.owner = None
        char.save()

delete_char_from_owners_account.short_description = "Deletes the association between this character and its current owner. This removes the character from the original owner's character listing."


class EVEObjectTypeAdmin(admin.ModelAdmin):
    list_display = ('ccp_id','name','group')
    search_fields = ['ccp_id', 'name','group__name']
    readonly_fields = ('ccp_id',)

admin.site.register(ObjectType, EVEObjectTypeAdmin)






class EVEESIKeyInline(admin.StackedInline):
    model = CharacterESIRoles

    fields = [x for x in CharacterESIRoles.__class__.__dict__.keys() if x.startswith('esi_')]
    readonly_fields = [x for x in CharacterESIRoles.__class__.__dict__.keys() if x.startswith('esi_')]
    can_delete = False
    verbose_name = "Key Permissions"
    extra = 0

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    #formfield_overrides = {
    #    models.TextField: {'widget': Textarea(attrs={'rows': 2, 'cols': 25})},
    #    models.BooleanField: {"form_class": forms.BooleanField, "widget":CheckboxInput()}
    #}


class EVEPlayerCharacterAdmin(admin.ModelAdmin):


    list_display = ('id', 'name', 'corporation')
    search_fields = ['id', 'name',]
    fields = ('name', 'corporation'
              )
    readonly_fields  = fields



    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(EVEPlayerCharacter, EVEPlayerCharacterAdmin)


class EVEPlayerCorporationInline(admin.TabularInline):
    model = EVEPlayerCorporation
    fields = ('name', 'ticker')
    extra = 0
    can_delete = False

class EVEPlayerAllianceAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'ticker',)
    search_fields = ['name', 'ticker']
    readonly_fields = ('name', 'ticker')


    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(EVEPlayerAlliance, EVEPlayerAllianceAdmin)

class EVEPlayerCorporationAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'ticker',  'alliance')
    search_fields = ['name', 'ticker']
    readonly_fields = ('name', 'ticker',  'alliance',)


admin.site.register(EVEPlayerCorporation, EVEPlayerCorporationAdmin)

