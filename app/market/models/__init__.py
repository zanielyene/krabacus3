import logging

from .trading_route import TradingRoute
from .market_order import MarketOrder
from .player_transaction import PlayerTransaction, TransactionLinkage
from .item_group import ItemGroup
from .market_history import MarketHistory
from .market_price_dao import MarketPriceDAO
from .shopping_list import ShoppingListItem
from .player_assets import AssetContainer, AssetEntry
from .log_models.history_scan_log import MarketHistoryScanLog
from .log_models.structure_scan_log import StructureMarketScanLog
from .log_models.player_order_scan_log import PlayerOrderScanLog
from .log_models.player_transaction_scan_log import PlayerTransactionScanLog
from .log_models.player_assets_scan_log import PlayerAssetsScanLog

from conf.huey_queues import general_queue

logger=logging.getLogger(__name__)

@general_queue.task()
def heat_market_price_dao():
    MarketPriceDAO.heat_cache()

@general_queue.task()
def heat_market_orders():
    MarketOrder.heat_cache()

@general_queue.task()
def heat_market_history():
    MarketHistory.heat_cache()

@general_queue.task()
def heat_cache():
    heat_market_price_dao()
    heat_market_orders()
    heat_market_history()
