import asyncio
import logging
from typing import List
from core.db import TimesScaleDb
from config import Config
from core.exchange.binance import PublicBinance, PublicFuturesBinance
from core.types import Symbol, Tf

logging.getLogger().setLevel(logging.INFO)

spot_api = PublicBinance()
futures_api = PublicFuturesBinance()

kline_lengths = {"1d": 365 * 5 * 24 * 60, "4h": 365 * 6 * 60, "1h": 190 * 24 * 60}


def save_to_csv(symbol, tf, candles):
    count = len(candles)
    if count > 0:
        # last_candle_time = int(candles.iloc[-1][0].timestamp())
        logging.info(f"{symbol} {tf} save {count} candles from exchange.")
        candles.to_csv(f"{Config.DATA_PATH}/candles/{symbol}_{tf}.csv", sep=";")


# async def import_candles(symbols: List[Symbol]):
#     tasks = []
#
#     now_ = datetime.utcnow()
#
#     for symbol in symbols:
#         for tf, len_minutes in kline_lengths.items():
#             delta = timedelta(minutes=len_minutes)
#             # spot_api.load_candles(symbol, tf, start_time=now_ - delta, end_time=now_)
#             tasks.append(
#                 loop.create_task(
#                     spot_api.load_candles(
#                         symbol, tf, start_time=now_ - delta, end_time=now_
#                     )
#                 )
#             )
#
#     return await asyncio.gather(*tasks, return_exceptions=True)


async def import_futures_symbols() -> List[Symbol]:
    await futures_api.load_exchange_info()
    return []


async def main():
    # await import_futures_symbols()
    db = TimesScaleDb(use_pool=True)
    await db.init()
    # symbols = list(futures_api.symbol_info.keys())[1:10]
    data = await db.get_symbol_status(active=True)
    for s in data:
        for tf in ['1d', '4h', '1h', '15m']:
            df = await db.load_candles(s['symbol'], Tf(tf))
            df['timestamp'] = df.index
            save_to_csv(s['symbol'], tf, df)
    # await import_candles(symbols)

    # for symbol, candles_by_tf in spot_api.candles.items():
    #     logging.info(f"Save {symbol} candles...")
    #     for tf, candles in candles_by_tf.items():
    #         df = candles_to_data_frame(candles)
    #         save_to_csv(symbol, tf, df)


if __name__ == "__main__":
    asyncio.run(main())
# loop.run_forever()
