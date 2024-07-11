import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import List
from config import Config
from core.ta.ta import (
    add_base_indicators,
    add_bound_levels,
    add_breakouts,
    get_price_levels,
    get_sup_resist_peaks,
    get_volume_levels,
    load_data,
)


def add_v_peaks(df: pd.DataFrame) -> go.Scatter:
    peaks_df = df[df["v_peak"]]
    fig = go.Scatter(
        x=peaks_df["timestamp"],
        y=peaks_df["dnv"],
        marker=dict(color="blue", size=3),
        mode="markers",
        showlegend=False,
    )
    return fig


def add_candles(df: pd.DataFrame) -> go.Candlestick:
    x = df["timestamp"]  # df.index
    candles = go.Candlestick(
        x=x,
        open=df["o"],
        high=df["h"],
        low=df["l"],
        close=df["c"],
        line=dict(width=0.5),
        # increasing=dict(line=dict(color="#C46A62"), fillcolor="#18D23C"),
        # decreasing=dict(line=dict(color="#616A6B"), fillcolor="#616A6B"),
        showlegend=False,
    )
    return candles


def add_volumes(df: pd.DataFrame) -> go.Bar:
    x = df["timestamp"]  # df.index
    volumes = go.Bar(
        x=x,
        y=df["dnv"],
        showlegend=False,
        marker=dict(color="darkgray", line=dict(color="darkgray", width=1.5)),
    )

    return volumes


def append_price_level_peaks(
    fig: go.Figure, df: pd.DataFrame, peaks: pd.Series, color: str
):
    points = go.Scatter(
        x=df.loc[peaks.index].timestamp,
        y=list(peaks),
        marker=dict(color=color, symbol="square-open", size=6),
        mode="markers",
        showlegend=False,
    )

    fig.add_trace(points)


def append_breakouts(fig: go.Figure, df: pd.DataFrame):
    colors = {"breakout_up": "DarkSalmon", "breakout_down": "DarkBlue"}
    for name in ["breakout_up", "breakout_down"]:
        df_s = df[df[name]]
        points = go.Scatter(
            x=df_s.timestamp,
            y=df_s.o,
            marker=dict(color=colors[name], symbol="circle", size=3),
            mode="markers",
            showlegend=False,
        )

        fig.add_trace(points)

    colors = {"signal_up": "DarkSalmon", "signal_down": "DarkBlue"}

    for name in ["signal_up", "signal_down"]:
        df_s = df[df[name]]
        points = go.Scatter(
            x=df_s.timestamp,
            y=df_s.o,
            marker=dict(color=colors[name], symbol="star", size=8),
            mode="markers",
            showlegend=False,
        )

        fig.add_trace(points)


def append_volume_levels(fig: go.Figure, levels: List[any]):
    # levels_df = df[(df["v_level"].isna()==False)]
    # levels = []
    # while len(levels_df) > 0:
    #
    #     v_level = levels_df['v_level'].iloc[0]
    #     curr_levels = levels_df[(df["v_level"] == v_level)]
    #     levels.append([curr_levels['timestamp'].iloc[0], curr_levels['timestamp'].iloc[-1], v_level])
    #     levels_df = levels_df[(df["v_level"] != v_level)]
    # print(levels)
    pass
    for level in levels:
        fig.add_shape(
            type="line",
            line=dict(color="blue", width=0.5),
            x0=level[0],
            y0=level[2],
            x1=level[1],
            y1=level[2],
            xref="x",
            yref="y",
            row=2,
            col=1,
        )
        fig.add_vline(x=level[1], line_width=1, line_dash="dash", line_color="blue", row=1, col=1)


def append_price_levels(fig: go.Figure, df, p_levels):
    min_date = df["timestamp"].iloc[0]
    max_date = df["timestamp"].iloc[-1]
    for p_level in p_levels:
        fig.add_shape(
            type="line",
            line=dict(color="red", width=1, dash="dash"),
            x0=min_date,
            y0=p_level,
            x1=max_date,
            y1=p_level,
            row=1,
            col=1,
            xref="x",
            yref="y",
        )


def plot_df(df: pd.DataFrame, title):
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.005,
        row_heights=[0.75, 0.25],
    )

    v_levels, v_levels_idx, df = get_volume_levels(df, backtesting=True)

    _up, _down, levels = get_sup_resist_peaks(df)

    fig.add_trace(add_candles(df), row=1, col=1)
    fig.add_trace(add_volumes(df), row=2, col=1)

    fig.add_trace(add_v_peaks(df), row=2, col=1)
    append_volume_levels(fig, v_levels)

    add_bound_levels(df, levels.values)
    add_breakouts(df)

    append_price_level_peaks(fig, df, _up, "blue")
    append_price_level_peaks(fig, df, _down, "green")
    append_price_levels(fig, df, get_price_levels(levels))
    append_breakouts(fig, df)
    # for level_peak in get_price_level_peaks(df):
    #     fig.add_trace(level_peak, row=1, col=1)

    fig.update_layout(
        xaxis1_rangeslider_visible=False,
        xaxis2_rangeslider_visible=True,
        xaxis2_type="date",
    )
    fig.update_layout(dragmode="zoom")
    fig.update_yaxes(fixedrange=False, row=2, col=1, range=[0, (df.dnv.max() - df.dnv.mean())])
    fig.update_layout(title_text=title)

    # fig.write_html("test.html")
    # fig.write_image(f"{title}.png")
    # fig.show()
    return fig
    # import chart_studio.plotly as py
    # py.iplot(fig, filename='jupyter-basic_bar')


def plot_chart(symbol: str, tf: str):
    title = f"{symbol}_{tf}"
    file_name = f"{Config.DATA_PATH}/candles/{title}.csv"
    # file_name = './data2/ETH-USDT_1h_1666857600.csv'
    df = load_data(file_name)
    df = add_base_indicators(df)
    fig = plot_df(df, title)
    return fig


if __name__ == "__main__":
    # file_name = './data2/BTC-USDT_4h_1666843200.csv'
    symbol = "DOGEUSDT"
    tf = "4h"
    title = f"{symbol}_{tf}"
    file_name = f"{Config.DATA_PATH}/candles/{title}.csv"
    # file_name = './data2/ETH-USDT_1h_1666857600.csv'
    df = load_data(file_name)
    df = add_base_indicators(df)
    fig = plot_df(df, title)
    fig.show()
