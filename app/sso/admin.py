from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.contrib.contenttypes.admin import GenericTabularInline
from sso.models import SSOUser


class SSOUserProfileInline(admin.StackedInline):
    model = SSOUser
    fk_name = 'user'
    max_num = 1
    readonly_fields = ('primary_character',)
    can_delete = False


# Define a new UserAdmin class
class SSOUserAdmin(UserAdmin):

    filter_horizontal = ['groups', 'user_permissions']



#admin.site.unregister(User)
#admin.site.register(User, SSOUserAdmin)
