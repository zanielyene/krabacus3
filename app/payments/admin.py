from django.contrib import admin

# Register your models here.
from .models import *
from .tasks import *

def update_subscription(modeladmin, request, queryset):
    for sub in queryset:
        sub.check_subscription_payments()
    return


class SubscriptionPaymentInline(admin.TabularInline):
    model = SubscriptionPayment
    fields = ('source_character', 'is_trial_payment','amount', 'journal_id', 'payment_time_actual', 'payment_read_time')
    #readonly_fields = ('source_character', 'journal_id', 'payment_time_actual', 'payment_read_time')
    readonly_fields = ['payment_read_time', 'payment_time_actual', 'journal_id']
    extra = 0

    #can_delete = False


class SubscriptionStatusAdmin(admin.ModelAdmin):
    model= SubscriptionStatus
    #filter_horizontal = ('item_groups',)
    list_display = ('__str__', 'active','credit_remaining','credit_consumed', 'subscription_last_updated', 'id' )
    search_fields = ['__str__']
    readonly_fields = ('user','credit_remaining','credit_consumed', 'subscription_last_updated', 'id' )
    inlines = [SubscriptionPaymentInline]
    actions = [update_subscription]

admin.site.register(SubscriptionStatus, SubscriptionStatusAdmin)

