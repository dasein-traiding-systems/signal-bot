from core.exchange.protectors.binance_request_limiter import BinanceRequestLimiter
from core.exchange.binance import PublicBinance, PublicFuturesBinance
from core.base import CoreBase
from core.types import RestMethod, Symbol, Tf, SymbolStr
from typing import Dict, List, Any, Tuple, Optional
from core.utils.data import candles_to_data_frame
from core.utils.utils import string_to_date, get_cluster_size
from core.utils.timeframe import tf_size_minutes, round_time_to_tf, get_time_shift
from core.db import TimesScaleDb
from core.exchange.common.mappers import symbol_to_binance, binance_to_symbol

from core.exchange.binance.common import get_filter_value
from datetime import datetime, timezone, timedelta
import os
import logging
import asyncio
import sys

BASE_URI = "https://api.binance.com/api/v3"
BASE_FUTURES_URI = "https://api.binance.com/api/v3"
MAX_CANDLES = os.getenv("MAX_CANDLES", 1000)
CANDLES_TIMEFRAMES = os.getenv("CANDLES_TIMEFRAMES", "1d,4h,1h,15m").split(",")
IMPORT_DATE_FROM = os.getenv("IMPORT_DATE_FROM", "01-01-2017")
IMPORT_DATE_TO = os.getenv("IMPORT_DATE_TO", None)


# IMPORTER_INFLUX_DB_HOST = os.getenv("IMPORTER_INFLUX_DB_HOST", "5.75.137.107")


class CandlesImporter(object):
    request_limiter = BinanceRequestLimiter()
    last_url_response = None
    db: TimesScaleDb = None

    def __init__(self, db: TimesScaleDb, date_from: Optional[str] = None, date_to: Optional[str] = None):
        self.spot_symbols: List[SymbolStr] = []
        self.exportable_symbols: List[SymbolStr] = []
        self.db = db
        self.date_from = None
        self.date_to = None

    async def init(self):
        # await self.db.init()
        await self.init_spot()
        await self.init_date_range()
        await self.db.init()
        await self.load_exportable_symbols()

    async def init_date_range(self):
        self.date_from = datetime.strptime(IMPORT_DATE_FROM, '%d-%m-%Y') if IMPORT_DATE_FROM else None
        self.date_to = datetime.strptime(IMPORT_DATE_TO, '%d-%m-%Y') \
            if IMPORT_DATE_TO else datetime.utcnow().replace(tzinfo=None)

    async def init_spot(self):
        content = await self.request_url("/exchangeInfo")

        rate_limits = content["rateLimits"]
        weight_limit_1m = int(get_filter_value(rate_limits, "REQUEST_WEIGHT", "limit", name_of_filter="rateLimitType"))
        raw_requests_5m = int(
            get_filter_value(
                rate_limits, "RAW_REQUESTS", "limit", name_of_filter="rateLimitType", default=weight_limit_1m,
            )
        )
        self.request_limiter.init(weight_limit_1m, raw_requests_5m)

        self.spot_symbols = [s['symbol'] for s in content["symbols"]
                             if s["isSpotTradingAllowed"] and s["quoteAsset"] == "USDT"]

    async def load_exportable_symbols(self):
        content = await self.request_url("/exchangeInfo", base_url=BASE_FUTURES_URI)
        futures_symbols = [s['symbol'] for s in content["symbols"] if s["quoteAsset"] == "USDT"
                           and "BULL" not in s["baseAsset"] and "BEAR" not in s["baseAsset"]]

        self.exportable_symbols = [s for s in futures_symbols if s in self.spot_symbols]
        # last_symbol = self.exportable_symbols.index("ADXUSDT")
        # self.exportable_symbols = self.exportable_symbols[last_symbol:]

    async def request_url(
            self,
            url: str,
            method: RestMethod = RestMethod.GET,
            params: Dict = {},
            headers: Dict = {},
            base_url: str = BASE_URI,
    ) -> Any:
        await self.request_limiter.delay(self.last_url_response)

        content, _ = await CoreBase.get_request().request_json(f"{base_url}{url}", method,
                                                               params=params, headers=headers)
        self.last_url_response = _
        if _.status != 200:
            logging.error(f"{_.url} {_.reason}")
        return content

    async def _load_candles(
            self,
            symbol: Symbol,
            tf: Tf = "1m",
            start_time: Optional[datetime] = None,
            end_time: Optional[datetime] = None,
    ):

        params = {"symbol": f"{symbol_to_binance(symbol)}", "interval": tf, "limit": MAX_CANDLES}
        rate_info = self.request_limiter.info
        logging.info(f" Import batch {symbol} candles {tf} - {start_time} - {end_time}. {rate_info}")

        if start_time is not None:
            params["startTime"] = int(int(start_time.replace(tzinfo=timezone.utc).timestamp()) * 1e3)

        if end_time is not None:
            params["endTime"] = int(int(end_time.replace(tzinfo=timezone.utc).timestamp()) * 1e3)

        content = await self.request_url(f"/klines", RestMethod.GET, params=params)

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

        return candles_to_data_frame(candles)
        # return candles

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

            await self.db.save_candles(symbol_to_binance(symbol), tf, candles_batch)
            return candles_batch

        end_time = round_time_to_tf(
            end_time or datetime.utcnow(), tf
        ) - timedelta(minutes=1)  # exclude LAST CANDLE

        # end_time = end_time or datetime.utcnow()
        start_time = start_time or get_time_shift(end_time, candle_size_minutes)

        logging.info(f"Import candles: {symbol}_{tf} - {start_time} - {end_time}.")

        start_time_ = get_time_shift(end_time, candle_size_minutes)

        candles = await load_candles_with_cache(start_time_, end_time)

        while len(candles) > 0 and candles.index[0] - timedelta(minutes=1) > start_time_:
            end_time = candles.index[0] - timedelta(minutes=1)
            start_time_ = get_time_shift(end_time, candle_size_minutes)

            candles = await load_candles_with_cache(start_time_, end_time)

        logging.info(f"Import candles: {symbol}_{tf} DONE.")

    async def import_symbol(self, symbol: Symbol, date_from: Optional[datetime]=None,
                            tfs: List[Tf]=CANDLES_TIMEFRAMES):
        symbol_str = symbol_to_binance(symbol)
        start_import = datetime.utcnow()

        for tf in tfs:
            d_from = date_from
            if d_from is None:
                d_from = (await self.db.get_symbol_status(symbol=symbol_str))["last_sync"]
                if d_from is None:
                    d_from = datetime.strptime("01-01-2017", '%d-%m-%Y')

            await self.load_candles(symbol, Tf(tf), d_from, self.date_to)

        await self.db.update_symbol_status_one_value(symbol_str, last_sync=start_import)

    async def import_symbol(self, symbol: Symbol, date_from: Optional[datetime] = None,
                            tfs: List[Tf] = CANDLES_TIMEFRAMES):
        symbol_str = symbol_to_binance(symbol)
        start_import = datetime.utcnow()

        for tf in tfs:
            d_from = date_from
            if d_from is None:
                d_from = (await self.db.get_symbol_status(symbol=symbol_str))["last_sync"]
                if d_from is None:
                    d_from = datetime.strptime("01-01-2017", '%d-%m-%Y')

            await self.load_candles(symbol, Tf(tf), d_from, self.date_to)

        await self.db.update_symbol_status_one_value(symbol_str, last_sync=start_import)

    async def import_all(self):
        total = len(self.exportable_symbols)
        for i, symbol in enumerate(self.exportable_symbols):
            await self.import_symbol(binance_to_symbol(symbol), self.date_from)
            logging.info(f"Imported of {symbol} ({i}/{total}) DONE.")

        logging.info(f"Imported  ALL from {self.date_from} to {self.date_to}")


async def get_symbol_names():
    def filter_usdt_symbols(symbols_: List[Symbol]) -> List[Symbol]:
        return [s for s in symbols_ if s[4:] == "USDT"]
    spot = PublicBinance()
    futures = PublicFuturesBinance()
    await futures.load_exchange_info()
    await spot.load_exchange_info()
    usdt_symbols_futures = filter_usdt_symbols(list(futures.symbol_info.keys()))
    usdt_symbols_spot = filter_usdt_symbols(list(spot.symbol_info.keys()))

    symbols = [s for s in usdt_symbols_futures if s in usdt_symbols_spot]
    skip = ["EOS", "BCH", "XLM", "ADA", "XTZ", "BAT", "ONT", "IOTA", "BAT"]
    list_to_import = [s for s in symbols if s[0] not in skip]
    return list_to_import


async def update_cluster_size():
    spot = PublicBinance()
    await spot.async_init()
    # list_to_import = await get_symbol_names()
    list_to_import = await ce.db.get_symbol_status(active=True)
    for s in list_to_import:
        symbol = binance_to_symbol(s['symbol'])
        price = spot.mark_prices[symbol]
        cluster_size = get_cluster_size(price)
        print(f'{symbol}: {price} - {cluster_size}')

        await ce.db.update_symbol_status_one_value(s['symbol'], cluster_size=cluster_size)

if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)

    ce = CandlesImporter()

    async def main():
        # 2022-11-17 18:03:12.994060
        await ce.init()
        # await ce.import_all()

        last_sync = string_to_date("2022-11-21 12:00:00")
        names =  await get_symbol_names()
        print(names)
        for symbol in names:
            await ce.db.add_symbol_status(symbol, last_sync, 0, True)
        # for symbol, tf in ce.db.symbol_tf.keys():
        #     if tf == Tf("1d"):
        #         await ce.db.update_symbol_status_one_value(symbol, active=True)

        await update_cluster_size()


    asyncio.run(main())
