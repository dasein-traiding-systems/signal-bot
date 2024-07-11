from typing import List

import pandas as pd
from ta.momentum import rsi
from ta.volatility import BollingerBands
from enum import Enum


class Position(Enum):
    LONG = "LONG"
    SHORT = "SHORT"


BB_WINDOW = 20
RSI_WINDOW = 14


def get_indicators(df_: pd.DataFrame, rsi_window: int = RSI_WINDOW, bb_window: int = BB_WINDOW):
    df = df_.copy()
    df["rsi"] = rsi(df.c, window=rsi_window)
    bb = BollingerBands(df.c, window=bb_window)
    df["bb_upper"] = bb.bollinger_hband()
    df['bb_lower'] = bb.bollinger_lband()
    df.dropna(inplace=True)

    return df


def should_buy(r: pd.Series) -> bool:
    return r.rsi < 30 and r.c < r.bb_lower


def should_sell(r: pd.Series) -> bool:
    return r.rsi > 70 and r.c > r.bb_upper


def get_profit(side: Position, open_price: float, close_price: float):
    if side == Position.SHORT:
        return (open_price - close_price) / open_price * 100
    else:
        return (close_price - open_price) / close_price * 100
