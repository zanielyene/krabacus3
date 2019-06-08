from django.contrib import admin

# Register your models here.
from .models import *


class TradingRouteAdmin(admin.ModelAdmin):
    model= TradingRoute
    filter_horizontal = ('item_groups',)
    list_display = ('__str__', 'creator', 'date_created' )
    search_fields = ['creator__username']


admin.site.register(TradingRoute, TradingRouteAdmin)


class MarketOrderAdmin(admin.ModelAdmin):
    model = MarketOrder
    readonly_fields = ['ccp_id','character','object_type']
    list_display = ('__str__', 'character', 'order_active','issued','location','object_type', 'is_buy_order')
    search_fields = ['ccp_id', 'character__name']


admin.site.register(MarketOrder, MarketOrderAdmin)


class MarketHistoryAdmin(admin.ModelAdmin):
    model = MarketHistory

    readonly_fields = ['object_type','date','region']
    list_display = ('object_type', 'region', 'date','order_count')
    search_fields = ['object_type__name', 'region__name']


admin.site.register(MarketHistory, MarketHistoryAdmin)


class TransactionLinkageSrcInline(admin.TabularInline):
    model = TransactionLinkage
    fk_name = "source_transaction"
    fields = ('destination_transaction', 'quantity_linked','date_linked', 'route')
    readonly_fields = ['destination_transaction', 'route']
    extra = 0
    can_delete = False


class TransactionLinkageDstInline(admin.TabularInline):
    model = TransactionLinkage
    fk_name = "destination_transaction"
    readonly_fields = ['source_transaction', 'route']
    fields = ('source_transaction', 'quantity_linked','date_linked', 'route')
    extra = 0
    can_delete = False


class PlayerTransactionAdmin(admin.ModelAdmin):
    model = PlayerTransaction

    readonly_fields = ['ccp_id', 'character', 'object_type', 'location', 'client_id', 'journal_ref_id']
    list_display = ['__str__', 'character', 'object_type','quantity', 'location','timestamp', 'journal_ref_id', 'is_buy']
    search_fields = ['ccp_id', 'character__name', 'object_type__name']
    inlines = [
        TransactionLinkageSrcInline,
        TransactionLinkageDstInline
        ]


admin.site.register(PlayerTransaction, PlayerTransactionAdmin)


class MarketHistoryScanLogAdmin(admin.ModelAdmin):
    model = MarketHistoryScanLog

    readonly_fields = ['region']
    list_display = ('region', 'scan_start', 'scan_complete')
    search_fields = ['region__name']


admin.site.register(MarketHistoryScanLog, MarketHistoryScanLogAdmin)


class StructureMarketScanLogAdmin(admin.ModelAdmin):
    model = StructureMarketScanLog

    readonly_fields = ['structure']
    list_display = ('structure', 'scan_start', 'scan_complete')
    search_fields = ['structure__name']


admin.site.register(StructureMarketScanLog, StructureMarketScanLogAdmin)


class PlayerOrderScanLogAdmin(admin.ModelAdmin):
    model = PlayerOrderScanLog

    readonly_fields = ['character']
    list_display = ('character', 'scan_start', 'scan_complete')
    search_fields = ['character__name']


admin.site.register(PlayerOrderScanLog, PlayerOrderScanLogAdmin)


class PlayerTransactionScanLogAdmin(admin.ModelAdmin):
    model = PlayerTransactionScanLog

    readonly_fields = ['character']
    list_display = ('character', 'scan_start', 'scan_complete')
    search_fields = ['character__name']


admin.site.register(PlayerTransactionScanLog, PlayerTransactionScanLogAdmin)


class PlayerAssetsScanLogAdmin(admin.ModelAdmin):
    model = PlayerAssetsScanLog

    readonly_fields = ['character']
    list_display = ('character', 'scan_start', 'scan_complete')
    search_fields = ['character__name']


admin.site.register(PlayerAssetsScanLog, PlayerAssetsScanLogAdmin)


class PlayerAssetContainerAdmin(admin.ModelAdmin):
    model = AssetContainer
    readonly_fields = ["character", "structure"]
    list_display = ["character", "name", "structure"]
    search_fields = ['character__name', 'name', 'structure__name']

admin.site.register(AssetContainer, PlayerAssetContainerAdmin)


class PlayerAssetAdmin(admin.ModelAdmin):
    model = AssetEntry
    readonly_fields = ["character", "structure", "container", "object_type"]
    list_display = ["character", "object_type","quantity", "structure", "container"]
    search_fields = ['character__name', 'structure__name', "container__name", "object_type__name"]


admin.site.register(AssetEntry, PlayerAssetAdmin)
