import numpy as np

from core.db import TimesScaleDb
from core.types import SymbolStr, Tf
from core.utils.timeframe import tf_size_minutes, round_time_to_tf
from datetime import datetime, timedelta
from core.utils.logs import add_traceback
import asyncio
from tools.backtesting.data_processor import add_candles, add_volumes
import plotly.graph_objects as go
from core.utils.logs import setup_logger
from plotly.subplots import make_subplots
from tools.candles_importer.importer import CandlesImporter
from config import Config
setup_logger()

symbol = SymbolStr("BTCUSDT")
tf = Tf("15m")
date_to = round_time_to_tf(datetime.utcnow(), tf)
date_from = date_to - timedelta(minutes=tf_size_minutes(tf) * 4 * 10)


async def main():
    try:
        db = TimesScaleDb(**Config.timescale_db_params)
        await db.init()
        ce = CandlesImporter(db=db)
        # await db.init()
        # trades = await db.load_trades(symbol=symbol, start_time=date_from, end_time=date_to)
        params = dict(tf=tf, start_time=date_from, end_time=date_to)
        clusters = await db.load_clusters(symbol, **params)
        # await db.load_candles(symbol, *params)
        candles = await db.load_candles(symbol, **params)
        candles["dnv"] = candles["v"] * candles["c"]
        # trades = trades[trades.index >= round_time_to_tf(trades.index[0], tf)]
        # min_price = trades.price.min()
        # max_price = trades.price.max()
        # clusters, min_max = get_clusters_by_tf(trades, min_price, max_price, step=10,
        #                                        tf_size=timedelta(minutes=tf_size_minutes(tf)))

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
        min_c = clusters.volume.min()
        max_c = clusters.volume.max()
        clusters["v_ratio"] = 1 + (clusters.volume - max_c) / max_c
        clusters["v_group"] = np.round_(clusters["v_ratio"] * 10)
        clusters["m_price"] = clusters[['price_from', 'price_to']].mean(axis=1)
        colors = ["#fff1f0", "#ffccc7", "#ffa39e", "#ff7875", "#ff4d4f", "#f5222d", "#cf1322", "#a8071a", "#820014", "#5c0011"]
        for i in range(1, 11, 1):
            data = clusters[clusters.v_group == i]
            c_fig = go.Scatter(
                x=data["timestamp"],
                y=data["m_price"],
                marker=dict(color="blue", size=i * 1.5), #colors[i-1]
                mode="markers",
                opacity=0.5,
                showlegend=False,
            )
            fig.add_trace(c_fig)
        # for i, c in clusters.iterrows():
        #     if c.volume > 0:
        #         # size = 1 + (c.volume - max_c) / max_c
        #         # print(c.timestamp, c.timestamp + timedelta(minutes=size), prices.right, prices.left)
        #         fig.add_shape(type="rect", xref="x", yref="y",
        #                       x0=c.timestamp, y0=c.price_from, x1=c.timestamp + timedelta(minutes=c.v_ratio*10),
        #                       y1=c.price_to,
        #                       line=dict(color="RoyalBlue"), row=1, col=1, opacity=0.5, fillcolor="RoyalBlue"
        #                       )
        # for date, data in clusters.items():
        #     for prices, volume in data.items():
        #         if volume > 0:
        #             size = 1 + (volume - min_max[1]) / min_max[1]
        #             print(date, date + timedelta(minutes=size), prices.right, prices.left)
        #             fig.add_shape(type="rect", xref="x", yref="y",
        #                           x0=date, y0=prices.right, x1=date + timedelta(minutes=size*10), y1=prices.left,
        #                           line=dict(color="RoyalBlue"), row=1, col=1, opacity=0.5, fillcolor="RoyalBlue"
        #                           )
        # print(clusters)
        fig.show()
    except Exception as e:
        print(add_traceback(e))


asyncio.run(main())
