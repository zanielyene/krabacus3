from django.contrib import admin

# Register your models here.
from .models import *


class UpdateMessageAdmin(admin.ModelAdmin):
    model= UpdateMessage
    list_display = ('subject', 'post_time', 'trigger_unread_widget' )
    search_fields = ['subject', 'message']


admin.site.register(UpdateMessage, UpdateMessageAdmin)


