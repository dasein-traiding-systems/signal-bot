from core.exchange.binance import PublicBinance, PublicFuturesBinance
import asyncio
from core.utils.logs import setup_logger, add_traceback
import logging
from datetime import datetime, timedelta
from core.utils.timeframe import tf_size_minutes
from core.types import Tf
import pandas as pd
import numpy as np
from core.db import TimesScaleDb
import plotly.graph_objects as go
import plotly

setup_logger()
futures = PublicFuturesBinance()
spot = PublicBinance()
# _load_candles



# import plotly.express as px


async def export_candle_delta():
    try:
        tf = Tf("1m")
        end_time = datetime.utcnow() - timedelta(hours=8)
        start_time = end_time - timedelta(minutes=tf_size_minutes(tf) * 1000)
        delta_df = pd.DataFrame()
        # logging.info()
        await futures.load_exchange_info()
        await spot.load_exchange_info()
        i = 0
        for symbol, si in list(futures.symbol_info.items()):
            try:
                if si.margin_asset == "USDT" and si.can_trade and symbol in spot.symbol_info.keys():
                    i += 1
                    spot_df = await spot.load_candles_standalone(symbol, tf, start_time=start_time, end_time=end_time)
                    futures_df = await futures.load_candles_standalone(symbol, tf, start_time=start_time,
                                                                       end_time=end_time)
                    for name in ['c']:  # 'o', 'h', 'l',
                        delta = np.round((spot_df[name] - futures_df[name]) / futures_df[name], 3) * 100
                        delta_df = delta_df.assign(**{f'{symbol}_{name}': delta})
                    logging.info(f"Processed {i} {symbol}")
            except Exception as e:
                logging.error(f"{symbol}: {add_traceback(e)}")

        return delta_df

    except Exception as e:
        logging.error(add_traceback(e))


def plot_spreads(delta_df: pd.DataFrame):
    fig = go.Figure()
    color_scale = plotly.colors.get_colorscale("Jet")
    pass
    for i, col_symbol in enumerate(delta_df.columns):
        data = delta_df[(delta_df[col_symbol].isna() == False) & (np.abs(delta_df[col_symbol]) > 0.5)]
        if len(data) > 0:
            fig.add_trace(go.Scatter(x=data.index, y=data[col_symbol],
                                     mode='lines+markers',
                                     name=col_symbol,
                                     # line=dict(width=1, color="blue"),
                                     marker=dict(
                                         size=4,
                                         color=i,  # set color equal to a variable
                                         colorscale='Viridis',  # one of plotly colorscales
                                         showscale=False)
                                     ))

    fig.show()


async def plot_spreads_db():
    fig = go.Figure()
    color_scale = plotly.colors.get_colorscale("Jet")
    db = TimesScaleDb()
    await db.init()
    df = await db.load_arbitrage_deltas()
    symbols = np.unique(df.symbol)
    for i, symbol in enumerate(symbols):
        data = df[df.symbol == symbol]
        if len(data) > 0 and np.max(data.delta_perc) > 0.23 and np.min(data.delta_perc) < -0.23:
            fig.add_trace(go.Scatter(x=data.timestamp, y=data.delta_perc,
                                     mode='markers',
                                     name=symbol,
                                     # line=dict(width=0.1, color="blue"),
                                     marker=dict(
                                         size=4,
                                         color=i,  # set color equal to a variable
                                         colorscale='Viridis',  # one of plotly colorscales
                                         showscale=False)
                                     ))

    fig.show()


async def main():
    try:
        # delta_df = await export_candle_delta()
        # delta_df.to_csv(f"{DATA_PATH}/delta1m.csv", sep=";")
        # delta_df = pd.read_csv(f"{DATA_PATH}/delta1m.csv", sep=";")
        # delta_df.set_index("timestamp", inplace=True)
        # plot_spreads(delta_df)

        await plot_spreads_db()
    except Exception as e:
        logging.error(add_traceback(e))


asyncio.run(main())
