from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

from core.base import CoreBase
from core.exchange.common.order_book import OrderBook
from core.exchange.binance.entities import Order

# from  new.exchange.common.order_book_partial import OrderBookBase
from core.types import Asset, RestMethod, Symbol, Tf, SymbolStr, OrderId
from core.utils.data import candles_to_data_frame
from core.exceptions import apiExceptionFactory


# @dataclass
class SymbolInfo:
    def __init__(
        self,
        tick_size: float,
        lot_size: float,
        min_amount: float,
        price_precision: float,
        amount_precision: float,
        quote_asset: Optional[str],
        base_asset: Optional[str],
        underlying_type: Optional[str],
        is_margin_allowed: Optional[bool]
    ):
        self.tick_size: float = tick_size
        self.lot_size: float = lot_size
        self.min_amount: float = min_amount
        self.price_precision: float = price_precision
        self.amount_precision: float = amount_precision
        self.quote_asset = quote_asset
        self.base_asset = base_asset
        self.underlying_type = underlying_type
        self.is_margin_allowed = is_margin_allowed
    #     self.status = status
    #
    # @property
    # def can_trade(self):
    #     return self.status == "TRADING"


class ExchangeCallback:
    def __init__(
        self,
        id: Any,
        symbol: Optional[Symbol],
        channel: str,
        callback: Callable,
        data: Optional[Any] = None,
    ):
        self.id = id
        self.symbol = symbol
        self.feed = channel
        self.callback = callback
        self.data = data


class BaseExchange:
    exchange = "public_exchange"
    base_uri = None

    def __init__(self):
        self.callbacks: List[ExchangeCallback] = []
        self.streams: Dict[str, datetime] = {}

    async def async_init(self):
        raise NotImplemented

    async def request_url(
        self,
        url: str,
        method: RestMethod = RestMethod.GET,
        params: Dict = {},
        headers: Dict = {},
        base_uri: Optional[str] = None
    ) -> Tuple[Any, Any]:
        base_uri_ = base_uri if base_uri is not None else self.base_uri
        content, _ = await CoreBase.get_request().request_json(
            f"{base_uri_}{url}", method, params=params, headers=headers
        )

        if _.status != 200:
            raise apiExceptionFactory(content=content, response=_)

        return content, _

    def add_callback(
        self,
        id: Any,
        channel: str,
        callback: Callable,
        data: Optional[Any] = None,
        symbol: Optional[Symbol] = None,
    ):
        ec = ExchangeCallback(
            id=id, symbol=symbol, channel=channel, callback=callback, data=data
        )
        self.callbacks.append(ec)

    def remove_callback(self, id: Any):
        self.callbacks = [ec for ec in self.callbacks if ec.id != id]

    async def subscribe(self, symbol: Symbol, feeds: List[str]):
        raise NotImplemented

    async def unsubscribe(self, symbol: Symbol, feeds: List[str]):
        raise NotImplemented


class PrivateExchange(BaseExchange):
    def __init__(self, api_key: str, api_secret: str):
        super().__init__()
        self.api_key = api_key
        self.api_secret = api_secret
        self.orders: Dict[Symbol, Dict[OrderId,Order]] = {}

    def _update_orders(self, order:Order):
        if order.symbol not in self.orders:
            self.orders[order.symbol] = {}

        if order.id not in self.orders[order.symbol]:
            self.orders[order.symbol][order.id] = order
        else:
            self.orders[order.symbol].update({order.id: order})


class PublicExchange(BaseExchange):
    def __init__(self):
        super().__init__()
        self.assets: List[Asset] = []
        self.order_books: Dict[Symbol, OrderBook] = {}
        self.trades: Dict[Symbol, List[Tuple[float, float, bool]]] = {}
        self.candles: Dict[Symbol, Dict[Tf, pd.DataFrame]] = {}
        self.candle_unclosed: Dict[Symbol, Dict[Tf, Optional[List[Any]]]] = {}
        self.symbol_info: Dict[Symbol, SymbolInfo] = {}
        self.mark_prices: Dict[Symbol, float] = {}
        self.candle_dnv: Dict[Symbol, Dict[Tf, float]] = {}

    def get_candles(self, symbol: SymbolStr, tf: Tf):
        candles_ = self.candles[symbol][tf]
        unclosed_candle = self.candle_unclosed[symbol][tf]
        if unclosed_candle is not None:
            return pd.concat([candles_, candles_to_data_frame([unclosed_candle])])

        return candles_

    def update_candles_dnv(self, symbol: Symbol, tf: Tf, price: float, volume: float):
        if symbol not in self.candle_dnv:
            self.candle_dnv[symbol] = {}

        if tf not in self.candle_dnv[symbol]:
            self.candle_dnv[symbol][tf] = 0

        self.candle_dnv[symbol][tf] = price * volume
