from core.db import TimesScaleDb
from core.types import SymbolStr, Tf
from core.utils.timeframe import tf_size_minutes, round_time_to_tf
from datetime import datetime, timedelta
from core.ta.clusters import get_clusters_by_tf
from core.utils.logs import add_traceback
import asyncio
from tools.backtesting.data_processor import add_candles, add_volumes
from core.exchange.common.mappers import binance_to_symbol
from core.utils.logs import setup_logger
from plotly.subplots import make_subplots
from tools.candles_importer.importer import CandlesImporter
import time

setup_logger()
db = TimesScaleDb()
ce = CandlesImporter()
symbol = SymbolStr("BTCUSDT")
tf = Tf("15m")
date_to = round_time_to_tf(datetime.utcnow(), tf)
date_from = date_to - timedelta(minutes=tf_size_minutes(tf)*4*10)


async def main():
    try:
        await db.init()
        trades = await db.load_trades(symbol=symbol, start_time=date_from, end_time=date_to)
        params = (tf, date_from, date_to)
        await ce.load_candles(binance_to_symbol(symbol), *params)
        candles = await db.load_candles(symbol, *params)
        candles["dnv"] = candles["v"] * candles["c"]
        # trades = trades[trades.index >= round_time_to_tf(trades.index[0], tf)]
        min_price = trades.price.min()
        max_price = trades.price.max()
        start = time.time()
        clusters, min_max = get_clusters_by_tf(trades, min_price, max_price, step=10,
                                               tf_size=timedelta(minutes=tf_size_minutes(tf)))
        end = time.time()
        print(f"TIME: {start - end}")
        candles['timestamp'] = candles.index
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=False,
            vertical_spacing=0.005,
            row_heights=[0.75, 0.25],
        )
        # fig.update_xaxes(range=[candles['timestamp'].min(), candles['timestamp'].max()], row=1, col=1)
        # fig.update_yaxes(range=[candles.l.min(), candles.h.max()], row=1, col=1)
        fig.add_trace(add_candles(candles), row=1, col=1)
        fig.add_trace(add_volumes(candles), row=2, col=1)
        for date, data in clusters.items():
            for prices, volume in data.items():
                if volume > 0:
                    size = 1 + (volume - min_max[1]) / min_max[1]
                    print(date, date + timedelta(minutes=size), prices.right, prices.left)
                    fig.add_shape(type="rect", xref="x", yref="y",
                                  x0=date, y0=prices.right, x1=date + timedelta(minutes=size*10), y1=prices.left,
                                  line=dict(color="RoyalBlue"), row=1, col=1, opacity=0.5, fillcolor="RoyalBlue"
                                  )
        # print(clusters)
        fig.show()
    except Exception as e:
        print(add_traceback(e))


asyncio.run(main())
