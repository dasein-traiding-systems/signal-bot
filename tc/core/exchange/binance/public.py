import asyncio
import logging
from datetime import timedelta
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple, Type

import pandas as pd
import ujson
import websockets
from websockets import WebSocketClientProtocol
from config import Config, MAX_CANDLES
# from config import MAX_CANDLES
from core.base import CoreBase
from core.exchange.binance.common import get_filter_value
from core.exchange.common.exchange import PublicExchange, SymbolInfo
from core.exchange.common.mappers import binance_to_symbol, symbol_to_binance
from core.exchange.common.order_book import OrderBook
from core.exchange.common.websocket import WebSocketBase
from core.exchange.protectors.binance_request_limiter import BinanceRequestLimiter
from core.types import RestMethod, Singleton, Symbol, Tf
from core.utils.data import candles_to_data_frame
from core.utils.logs import setup_logger, add_traceback
from core.utils.timeframe import tf_size_minutes, round_time_to_tf, get_time_shift
from datetime import timezone, datetime
from core.providers.data_provider import DataProvider, TimescaleDataProvider
import math

CANDLES_FEED_NAMES = ["kline_1m", "kline_1h"]
DETAILS_FEED_NAMES = ["trade", "depth", "markPrice"]
BASE_URI = "https://api.binance.com/api/v3"
MARGIN_URI = "https://api.binance.com/sapi/v1/margin"
# https://fapi.binance.com/fapi/v1/exchangeInfo
WSS_URL = "wss://stream.binance.com:443/ws/"

MAX_TRADES = 500
WS_TIMEOUT = 0
WS_MSG_TIME = 0.25

LEVEL_CANDLES_LENGTH = {
    "1d": dict(days=365 * 5),
    "4h": dict(hours=2000 * 4),
    "1h": dict(hours=2000),
    "15m": dict(hours=2000 / 4),
    "1m": dict(minutes=2000)
}


def paginate(data: List, page_length: int):
    return [data[i: i + page_length] for i in range(0, len(data), page_length)]


def side_data_to_float(data):
    return [(float(i[0]), float(i[1])) for i in data]


def get_symbol_info(symbol_info: Dict[str, Any], is_futures: bool = False):
    filter = symbol_info["filters"]
    tick = float(get_filter_value(filter, "PRICE_FILTER", "tickSize"))
    lot = float(get_filter_value(filter, "LOT_SIZE", "stepSize"))

    name_of_notional = "notional" if is_futures else "minNotional"

    min_amount = float(get_filter_value(filter, "MIN_NOTIONAL", name_of_notional))

    price_precision = symbol_info["baseAssetPrecision"]
    #             price_precision = -round(math.log10(tick))
    amount_precision = -round(math.log10(lot))

    name_of_quote = 'marginAsset' if is_futures else 'quoteAsset'
    base_asset = symbol_info.get("baseAsset", None)

    quote_asset = symbol_info.get(name_of_quote, None)
    underlying_type = symbol_info.get('underlyingType', None)
    is_margin_allowed = symbol_info.get("isMarginTradingAllowed", None)
    # status = symbol_info.get('status', None)
    symbol_info = SymbolInfo(tick, lot, min_amount, price_precision, amount_precision, quote_asset, base_asset,
                             underlying_type, is_margin_allowed)
    return symbol_info


class PublicBinance(PublicExchange, metaclass=Singleton):
    exchange = "binance"
    logger_name = "public_binance"
    base_uri = BASE_URI
    wss_url = WSS_URL
    request_limiter = BinanceRequestLimiter()
    last_url_response = None

    def __init__(self, on_trade_callback: Optional[Callable] = None, on_candle_callback: Optional[Callable] = None,
                 on__all_price_callback: Optional[Callable] = None,
                 data_provider: Optional[TimescaleDataProvider] = None):
        super().__init__()
        self.wsb: Optional[WebSocketBase] = None
        self.debug = 0
        self.on_trade_callback = on_trade_callback
        self.on_candle_callback = on_candle_callback
        self.on_all_price_callback = on__all_price_callback
        self.logger = setup_logger(self.logger_name)
        self.data_provider = data_provider

    async def async_init(
            self, on_connect_callback: Optional[Callable[[], Coroutine]] = None
    ):
        await self.data_provider.init()
        self.wsb = WebSocketBase(
            self.logger_name,
            self.ws_connect_public,
            self.ws_on_message,
            timeout=WS_TIMEOUT,
            on_reconnect=self.reconnect_streams,
            on_connect=on_connect_callback,
            logger=self.logger,
        )
        # Important - load_exchange_info also set-up Request Balancer
        await self.load_exchange_info()
        await self.load_mark_prices()

        await asyncio.sleep(0)

    @property
    def is_connected(self):
        return self.wsb is not None and self.wsb.is_connected

    def get_dnv(self, symbol: Symbol, tf: Tf):
        return self.candle_dnv.get(symbol, {}).get(tf, None)

    def get_mark_price(self, symbol: Symbol):
        return self.mark_prices[symbol]

    async def wait_for_connection(self):
        self.logger.info("Waiting for connection...")
        while not self.is_connected:
            await asyncio.sleep(1)

        self.logger.info("Connected.")

    async def send_message(self, symbols: List[Symbol] = [], feeds: List[str] = [],
                           global_feeds: Optional[List[str]] = None, method: str = "SUBSCRIBE"):
        # <symbol>@trade
        # <symbol>@depth OR <symbol>@depth@100ms Update Speed: 1000ms or 100ms
        # !markPrice@arr@1s
        # !ticker @ arr
        # !miniTicker@arr - mark price

        if global_feeds is not None:
            await self._send_message_ws(method, global_feeds)

        for page_symbols in paginate(symbols, 10):
            params = []
            for symbol in page_symbols:
                params += [f"{symbol_to_binance(symbol).lower()}@{f}" for f in feeds]

            if method == "SUBSCRIBE":
                for p in params:
                    self.streams[p] = datetime.utcnow()
            else:
                for p in params:
                    try:
                        del self.streams[p]
                    except KeyError:
                        pass

            await self._send_message_ws(method, params)

    async def _send_message_ws(self, method: str, params: List[str], id: int = 1):
        msg = {"method": method.upper(), "params": params, "id": id}

        self.logger.info(f"Send to WS {method} with {params}")

        await self.wsb.ws.send(ujson.dumps(msg))
        await asyncio.sleep(WS_MSG_TIME)

    async def subscribe(
            self, symbols: List[Symbol], feeds: List[str] = DETAILS_FEED_NAMES
    ):
        tasks = []
        # if "markPrice" in feeds:
        #     tasks.append(loop.create_task(self.load_mark_prices()))
        self.logger.info("Preload data...")

        for symbol in symbols:
            if "depth" in feeds:
                tasks.append(CoreBase.get_loop().create_task(self.load_order_books(symbol)))
            # if "trade" in feeds:
            #     tasks.append(CoreBase.get_loop().create_task(self.load_trades(symbol)))

            self.candle_unclosed[symbol] = {}

            kline_tfs = [Tf(f.split("_")[1]) for f in feeds if "kline" in f]
            now_ = datetime.utcnow()
            for tf in kline_tfs:
                delta = timedelta(**LEVEL_CANDLES_LENGTH[tf])
                await self.load_candles(
                    symbol, tf, start_time=now_ - delta, end_time=now_
                )
                self.candle_unclosed[symbol][tf] = None
        self.logger.info("Do Subscribe to WS...")
        await self.send_message(symbols=symbols, feeds=feeds, method="SUBSCRIBE")

    async def unsubscribe(
            self, symbols: List[Symbol], feeds: List[str] = DETAILS_FEED_NAMES
    ):
        for symbol in symbols:
            if "trade" in feeds:
                self.trades[symbol] = []
            if "depth" in feeds:
                self.order_books[symbol] = OrderBook()

            kline_tfs = [f.split("_")[1] for f in feeds if "kline" in f]

            for tf in kline_tfs:
                self.candles[symbol][Tf(tf)] = []

        return await self.send_message(symbols=symbols, feeds=feeds, method="UNSUBSCRIBE")

    async def unsubscribe_by_id(self, stream_id: Any):
        symbols = []
        feeds = []
        for c in self.callbacks:
            if c.id == stream_id:
                symbols.append(c.symbol)
                feeds.append(c.feed)
                break

        return await self.unsubscribe(symbols, feeds)

    async def reconnect_streams(self):
        if len(self.streams) > 0:
            self.logger.warning("Reconnecting... TODO: reload candles etc..")
            #  TODO: reload candles etc..
            for streams in paginate(list(self.streams.keys()), 20):
                await self._send_message_ws("SUBSCRIBE", streams)

    async def ws_connect_public(self) -> WebSocketClientProtocol:
        stream_name = f"{self.wss_url}stream"
        self.logger.info(
            f"Connecting to {self.exchange} '{stream_name}' public websocket"
        )
        conn = await websockets.connect(
            stream_name, ping_interval=None, loop=CoreBase.get_loop(), max_queue=5000
        )
        # await self.reconnect_streams()
        return conn

    async def ws_on_message(self, msg):
        try:
            if type(msg) is list:
                if self.on_all_price_callback is not None:
                    self.on_all_price_callback(msg)
                return

            if "result" in msg:
                self.logger.warning(f"wss msg: {msg}")
                return

            channel = msg["e"]
            symbol = binance_to_symbol(msg["s"])

            # self.streams[channel] = datetime.utcnow()

            if channel in ["trade", "aggTrade"]:  # in msg['stream']:
                # https://www.programiz.com/python-programming/methods/built-in/zip
                if self.on_trade_callback is not None:
                    await self.on_trade_callback(msg["s"].upper(), float(msg["p"]), float(msg["q"]), msg["m"],
                                                 datetime.utcfromtimestamp(msg["T"] / 1e3))
                else:
                    item = (float(msg["p"]), float(msg["q"]), msg["m"])
                    self.trades[symbol].append(item)
                    self.trades[symbol] = self.trades[symbol][-MAX_TRADES:]

            elif channel == "depthUpdate":
                self.order_books[symbol].update_sides(
                    side_data_to_float(msg["b"]), side_data_to_float(msg["a"])
                )

            elif channel == "kline":
                c = msg["k"]
                tf = Tf(c["i"])
                c_ = float(c["c"])
                v_ = float(c["v"])
                o_ = float(c["o"])
                h_ = float(c["h"])
                l_ = float(c["l"])
                c_time = datetime.utcfromtimestamp(c["t"] / 1e3)

                self.mark_prices[symbol] = c_
                self.update_candles_dnv(symbol, tf, c_, v_)
                candle_closed = c["x"]

                candle_item = [c_time, o_, h_, l_, c_, v_]
                self.candle_unclosed[symbol][tf] = candle_item
                if candle_closed:
                    self.candles[symbol][tf] = pd.concat(
                        [self.candles[symbol][tf], candles_to_data_frame([candle_item])]
                    )

                if self.on_candle_callback is not None:
                    await self.on_candle_callback(msg["s"].upper(), tf, candle_closed, candle_item,
                                                  datetime.utcfromtimestamp(c["T"] / 1e3))
                else:
                    if candle_closed:
                        await asyncio.gather(
                            *[
                                asyncio.create_task(c.callback(symbol, tf, c_time))
                                for c in self.callbacks
                                if c.feed == f"kline_{tf}" and c.symbol == symbol
                            ]
                        )

            # elif channel == "markPriceUpdate":
            #     p = float(data["p"])
            #     self.mark_prices[symbol] = p
            #     await asyncio.gather(
            #         *[asyncio.create_task(c.callback(symbol, p)) for c in self.callbacks if c.feed == f"mark_price"]
            #     )
        except Exception as e:
            self.logger.error(add_traceback(e))

    async def load_order_books(self, symbol: Symbol):
        content, _ = await self.request_url(
            f"/depth",
            RestMethod.GET,
            params={"symbol": f"{symbol_to_binance(symbol).upper()}"},
        )

        self.order_books[symbol] = OrderBook()
        self.order_books[symbol].update_sides(
            side_data_to_float(content["bids"]), side_data_to_float(content["asks"])
        )
        pass

    async def get_24h_statistics(self) -> pd.DataFrame:
        content, _ = await self.request_url(f"/ticker/24hr", RestMethod.GET)
        return pd.DataFrame(content)

    async def load_trades(self, symbol: Symbol):
        content, _ = await self.request_url(
            f"/trades",
            RestMethod.GET,
            params={
                "symbol": f"{symbol_to_binance(symbol).upper()}",
                "limit": MAX_TRADES,
            },
        )
        # also : time, 'isBestMatch', quoteQty
        self.trades[symbol] = [
            (float(i["price"]), float(i["qty"]), i["isBuyerMaker"]) for i in content
        ]
        pass

    async def load_mark_prices(self):
        content, _ = await self.request_url(f"/ticker/price", RestMethod.GET)
        self.mark_prices = {
            binance_to_symbol(i["symbol"]): float(i["price"]) for i in content
        }

    async def load_candles_standalone(self,
                                      symbol: Symbol,
                                      tf: str = "1m",
                                      start_time: Optional[datetime] = None,
                                      end_time: Optional[datetime] = None,
                                      ):
        candles = await self._load_candles(symbol, tf, start_time, end_time)

        return candles

    async def _load_candles(
            self,
            symbol: Symbol,
            tf: str = "1m",
            start_time: Optional[datetime] = None,
            end_time: Optional[datetime] = None,
    ):

        params = {
            "symbol": f"{symbol_to_binance(symbol).upper()}",
            "interval": tf,
            "limit": MAX_CANDLES,
        }
        self.logger.debug(f"{symbol} candles {tf} - {start_time} - {end_time}.")

        if start_time is not None:
            params["startTime"] = int(int(start_time.replace(tzinfo=timezone.utc).timestamp()) * 1e3)

        if end_time is not None:
            params["endTime"] = int(int(end_time.replace(tzinfo=timezone.utc).timestamp()) * 1e3)

        content, _ = await self.request_url(f"/klines", RestMethod.GET, params=params)
        if _.status != 200:
            logging.error(f"{_.url}")
            # raise KeyError(content['msg'])
        try:
            candles = [
                [
                    datetime.utcfromtimestamp(c[0] / 1e3),
                    float(c[1]),
                    float(c[2]),
                    float(c[3]),
                    float(c[4]),
                    float(c[5]),
                ]
                for c in content
            ]
        except Exception as e:
            self.logger.error(e)
            candles = []
        return candles_to_data_frame(candles)

    async def load_candles(
            self,
            symbol: Symbol,
            tf: Tf = "1m",
            start_time: Optional[datetime] = None,
            end_time: Optional[datetime] = None,
    ):
        candle_size_minutes = tf_size_minutes(tf)

        async def load_candles_with_cache(from_time, to_time):
            if (to_time - from_time) <= timedelta(minutes=candle_size_minutes):  # *2
                return candles_to_data_frame([])

            candles_batch = await self._load_candles(symbol, tf, from_time, to_time)
            if len(candles_batch) == 0:
                return candles_to_data_frame([])

            if self.data_provider is not None:
                await self.data_provider.save_candles(symbol=symbol_to_binance(symbol), tf=tf, candles=candles_batch)
            return candles_batch

        end_time = round_time_to_tf(
            end_time or datetime.utcnow(), tf
        ) - timedelta(minutes=1)  # exclude LAST CANDLE

        # end_time = end_time or datetime.utcnow()
        start_time = start_time or get_time_shift(end_time, candle_size_minutes)

        self.logger.info(f"Preload candles: {symbol}_{tf} - {start_time} - {end_time}.")
        candles_db = pd.DataFrame()
        if self.data_provider is not None:
            candles_db = await self.data_provider.load_candles(symbol_to_binance(symbol), tf,
                                                               start_time, end_time)

        start_time_ = (
            candles_db.index[-1] if len(candles_db) > 0 else get_time_shift(end_time, candle_size_minutes)
        )

        candles = await load_candles_with_cache(start_time_, end_time)

        candles_total = pd.concat([candles_db, candles])

        while len(candles) > 0 and candles.index[0] > start_time_:
            end_time = candles.index[0] - timedelta(minutes=1)
            start_time_ = get_time_shift(end_time, candle_size_minutes)

            candles = await load_candles_with_cache(start_time_, end_time)
            candles_total = pd.concat([candles_total, candles])

        if symbol not in self.candles:
            self.candles[symbol] = {}

        self.candles[symbol][tf] = candles_total

        last_candle = candles_total.iloc[-1]
        self.update_candles_dnv(
            symbol=symbol, tf=tf, price=last_candle.c, volume=last_candle.v
        )
        self.logger.info(f"Preload candles: {symbol}_{tf} DONE.")

        return candles_total

    def get_asset_quantity(self, symbol: Symbol, price: float, quantity_usd: float) -> float:
        lot_size = self.symbol_info[symbol].lot_size
        q, _ = divmod(quantity_usd / price, lot_size)  # total lots
        return q * lot_size

    async def load_exchange_info(self) -> List[str]:
        # [{'rateLimitType': 'REQUEST_WEIGHT', 'interval': 'MINUTE', 'intervalNum': 1, 'limit': 1200},
        #  {'rateLimitType': 'ORDERS', 'interval': 'SECOND', 'intervalNum': 10, 'limit': 50},
        #  {'rateLimitType': 'ORDERS', 'interval': 'DAY', 'intervalNum': 1, 'limit': 160000},
        #  {'rateLimitType': 'RAW_REQUESTS', 'interval': 'MINUTE', 'intervalNum': 5, 'limit': 6100}]
        content, _ = await self.request_url("/exchangeInfo")

        rate_limits = content["rateLimits"]
        weight_limit_1m = int(
            get_filter_value(
                rate_limits, "REQUEST_WEIGHT", "limit", name_of_filter="rateLimitType"
            )
        )
        raw_requests_5m = int(
            get_filter_value(
                rate_limits,
                "RAW_REQUESTS",
                "limit",
                name_of_filter="rateLimitType",
                default=weight_limit_1m,
            )
        )

        self.request_limiter.init(weight_limit_1m, raw_requests_5m)
        symbols_str_list = []
        for s in content["symbols"]:
            if s["isSpotTradingAllowed"]:
                symbols_str_list.append(s['symbol'])
                self.symbol_info[s['symbol']] = get_symbol_info(
                    s, is_futures=False
                )
            else:
                pass
                # logging.info(f'Symbol: {s["symbol"]} - trading not allowed.')

        return symbols_str_list

    async def request_url(
            self,
            url: str,
            method: RestMethod = RestMethod.GET,
            params: Dict = {},
            headers: Dict[str, str] = {},
            base_uri: Optional[str] = None
    ) -> Tuple[Any, Any]:
        await self.request_limiter.delay(self.last_url_response)

        content, _ = await super().request_url(
            url, method, params=params, headers=headers, base_uri=base_uri
        )
        self.last_url_response = _

        return content, _


if __name__ == "__main__":
    binance = PublicBinance()
    CoreBase.get_loop().create_task(binance.async_init())
    # loop.run_until_complete(binance.wait_for_connection())
    # while not binance.is_connected:
    #     sleep(1)
    CoreBase.get_loop().run_until_complete(binance.load_exchange_info())
    btc_usdt = ("BTC", "USDT")

    symbols = list(binance.symbol_info.keys())[:200]


    # symbols = [btc_usdt, ('WAVES', 'USDT')]

    async def callback_candle_1m(symbol, tf, candle_time):
        logging.info(f"Callback: {symbol}-{tf} {candle_time}")


    for s in symbols:
        binance.add_callback(
            id=f"1234-{s}", channel="kline_1m", symbol=s, callback=callback_candle_1m
        )

    CoreBase.get_loop().create_task(binance.subscribe(symbols, DETAILS_FEED_NAMES + ["kline_1m"]))
    CoreBase.get_loop().run_forever()
