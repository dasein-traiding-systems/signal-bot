import datetime
from typing import Any, Callable, List, Tuple, Union

import numpy as np
import pandas as pd
from scipy import signal as sig


def load_data(file_name: str) -> pd.DataFrame:
    df = pd.read_csv(file_name, sep=";")
    df.drop(['timestamp.1'], axis=1, inplace=True)
    # df["timestamp"] = pd.to_datetime(df["date"])

    df.set_index("timestamp", inplace=True)
    # df.drop(df.columns[[0,1]], axis=1, inplace=True)
    return df


def add_base_indicators(df: pd.DataFrame) -> pd.DataFrame:
    # df["dnv"] = df["v"] * df["c"]
    df["hl"] = df["h"] - df["l"]
    df["oc"] = np.abs(df["o"] - df["c"])
    df["side"] = df.apply(lambda row: -1 if row["o"] > row["c"] else 1, axis=1)
    return df


def convert_index_to_timestamp(lst:List[Any], df)->List[Any]:
    result = []
    for l in lst:
        result.append([df.timestamp[l[0]], df.timestamp[l[1]], l[2]])

    return result


def get_volume_levels(
    df: pd.DataFrame, backtesting=False
) -> Union[List[any], Tuple[List[Any], List[Any], pd.DataFrame]]:
    df["dnv"] = df.v * df.c
    df["timestamp"] = df.index
    df = df.reset_index(drop=True)

    # drop N largest PEAKS
    N_LARGEST_TO_DROP = 3
    df_ = df.drop(df.nlargest(N_LARGEST_TO_DROP, 'dnv').index, errors="ignore")
    # find peaks
    peaks = sig.find_peaks(df_["dnv"], height=df_["dnv"].mean() * 3, threshold=df_["dnv"].mean(), distance=90)
    levels = []

    # splice by "seasons" and calc levels
    v_level = prev_v_level = None
    for interval in pd.cut(df.index, peaks[0]).categories:
        prev_v_level = v_level
        season = df.loc[interval.left:interval.right]
        dnv = season.dnv
        v_level = dnv.mean() * 2 # + dnv.min() * 2

        # make smooth transition to next level
        if prev_v_level is not None:
            v_level = np.mean([v_level, prev_v_level])

        levels.append([season.index[0], season.index[-1], v_level])
        pass

    # fix last level index
    levels[-1][1] = df.index[-1]

    if backtesting:
        df['v_peak'] = False
        df.v_peak[df.index.isin(peaks[0])]  = True
        df['v_level'] = np.nan
        for level in levels:
            df['v_level'].loc[level[0]:level[1]] = level[2]

        df["v_level_breakout"] = df.apply(lambda row: row["dnv"] >= row["v_level"], axis=1)
        levels_by_timestamp = convert_index_to_timestamp(levels, df)
        df.index = df['timestamp']
        return levels_by_timestamp, levels, df

    return convert_index_to_timestamp(levels, df)

    # df["v_peak"] = 0
    # df["v_peak"] = df.iloc[peaks[0]]["dnv"]
    # v_peaks = []
    # prev_n = 0
    # df["v_level"] = np.nan
    # for i, n in enumerate(peaks[0]):
    #
    #     if prev_n > 0:
    #         last_n = n
    #         if i == len(peaks[0]) - 1:  # last bounds = last candle
    #             last_n = len(df) - 1
    #
    #         v_period = df.iloc[prev_n:last_n]["dnv"]
    #         avg = v_period.mean() + v_period.min() * 2
    #         avg_l = avg
    #
    #         if len(v_peaks) > 0:
    #             prev_avg = v_peaks[i - 2][2]
    #             avg_l = np.mean([avg_l, prev_avg])
    #
    #             if (
    #                 prev_avg > avg_l + prev_avg / 10
    #             ):  # Если прошлый уровень на 10% <> текущего оставляем
    #                 avg_l = prev_avg
    #         df.loc[last_n:, "v_level"] = avg_l
    #         v_peaks.append(
    #             (df.loc[prev_n, "timestamp"], df.loc[last_n, "timestamp"], avg_l)
    #         )
    #
    #     prev_n = n


def get_sup_resist_peaks(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
    num_candles = 15

    l_up_result = pd.Series(dtype=pd.Float64Dtype())
    l_down_result = pd.Series(dtype=pd.Float64Dtype())

    for i in ["h", "l"]:
        extrema_down = sig.argrelextrema(df[i].values, np.less_equal, order=num_candles)
        extrema_up = sig.argrelextrema(
            df[i].values, np.greater_equal, order=num_candles
        )
        l_up = df.iloc[extrema_up[0]][i]
        l_down = df.iloc[extrema_down[0]][i]

        l_up_result = pd.concat([l_up_result, l_up])
        l_down_result = pd.concat([l_down_result, l_down])

    l_all = pd.concat([l_up_result, l_down_result]).dropna()
    return l_up_result, l_down_result, l_all


def get_price_levels(peaks: pd.Series) -> np.array:
    first_level = peaks.iloc[0]
    levels = [(first_level, [first_level])]

    def diff_price(p1, p2):
        diff = abs(p1 - p2)
        p = diff / p1
        return p

    diff_p = 0.05
    for level_peak in peaks[1:]:
        has_level = False
        for l in levels:
            if diff_price(level_peak, l[0]) <= diff_p:
                l[1].append(level_peak)
                has_level = True
                break

        if not has_level:
            levels.append((level_peak, [level_peak]))

    # remove weak levels
    results = []

    for l in levels:
        if len(l[1]) > 2:
            results.append(np.mean(l[1]))

    return np.array(results)


def select(arr: np.array, condition: Any, default=np.nan) -> float:
    items = arr[condition]
    return items[0] if len(items) > 0 else default


def add_bound_levels(df: pd.DataFrame, p_levels: np.array):
    p_levels.sort()

    df["resistance_level"] = df.apply(
        lambda row: select(p_levels, row["c"] <= p_levels), axis=1
    )
    df["c_prev"] = df.c.shift(-1)
    df["resistance_level_prev"] = df.resistance_level.shift(-1)
    df["support_level"] = df.apply(
        lambda row: select(p_levels, row["c"] >= p_levels), axis=1
    )
    df["support_level_prev"] = df.support_level.shift(-1)


def add_breakouts(df: pd.DataFrame):
    df["breakout_up"] = df.apply(
        lambda row: row["c_prev"] <= row["resistance_level_prev"] <= row["c"], axis=1
    )
    df["breakout_down"] = df.apply(
        lambda row: row.shift(-1)["c_prev"]
        >= row.shift(-1)["support_level_prev"]
        >= row["c"],
        axis=1,
    )
    df["signal_up"] = df.apply(
        lambda row: row["v_level_breakout"] and row["breakout_up"], axis=1
    )
    df["signal_down"] = df.apply(
        lambda row: row["v_level_breakout"] and row["breakout_down"], axis=1
    )
    pass
