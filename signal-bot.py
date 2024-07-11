from patch_submod import dummy  # <- REQUIRED
from tc.core.exchange.binance.public_futures import PublicFuturesBinance
from tc.core.utils.telegram import send_to_telegram, get_telegram_chat_updates
import asyncio
from tc.core.types import Symbol, OrderType, Side, SymbolStr, SideEffectType, OrderStatus, Tf
from datetime import datetime, timedelta
from typing import Optional, Union, List, Any
from tc.core.utils.logs import setup_logger, add_traceback
from tc.core.providers.data_provider import TimescaleDataProvider
from utils import get_indicators, should_buy, should_sell, BB_WINDOW
from tc.config import Config
import logging
dummy()
SIGNAL_FEEDS = ["kline_1h", "kline_4h", "kline_1d"]
config = Config.load_from_env()
setup_logger(config=config)
MAX_SYMBOLS = 30
CHANNEL_ID = "-854973697" # Dasein Signal


class TradingBot(object):
    def __init__(self):
        db_provider = TimescaleDataProvider(config)
        self.client = PublicFuturesBinance(data_provider=db_provider)
        self.symbols: List[SymbolStr] = []

    async def load_symbols(self):
        self.symbols = [symbol for symbol, info in self.client.symbol_info.items()][:MAX_SYMBOLS]
        logging.info(f"Symbols to follow {self.symbols}")
        return self.symbols

    async def init(self):
        logging.info("Trading bot init...")
        self.client.on_candle_callback = self.on_candle_callback
        await self.client.async_init()
        await self.client.wait_for_connection()
        await self.load_symbols()
        await self.client.subscribe(self.symbols, SIGNAL_FEEDS)

    async def preload(self):
        for symbol, tfs in self.client.candles.items():
            for tf in tfs:
                await self.trade_decision(symbol, tf)

    async def start(self):
        logging.info("Starting bot...")
        await self.init()
        await self.preload()

    async def trade_decision(self, symbol: SymbolStr, tf: Tf):
        candles = get_indicators(self.client.candles[symbol][tf].iloc[-1*(BB_WINDOW + 1):])
        row = candles.iloc[-1]
        msg = f"{symbol}_{tf} rsi: {row.rsi} bb: {row.bb_upper} | {row.c} | {row.bb_lower}"

        if should_buy(row):
            await send_to_telegram(f"{msg} => <strong>BUY</strong>", CHANNEL_ID)
        elif should_sell(row):
            await send_to_telegram(f"{msg} => <strong>SELL</strong>", CHANNEL_ID)

    async def on_candle_callback(self, symbol: SymbolStr, tf: Tf, candle_closed: bool, candle_item: List[Any],
                                 close_time: datetime):
        try:
            if candle_closed:
                await self.trade_decision(symbol, tf)
        except Exception as e:
            logging.error(add_traceback(e))


if __name__ == "__main__":
    bot = TradingBot()

    async def main():

        try:
            await bot.start()
            await send_to_telegram("Bot started", CHANNEL_ID)
            logging.info("Started.")
            while True:
                await asyncio.sleep(5)
        except Exception as e:
            logging.error(add_traceback(e))

    asyncio.run(main())
