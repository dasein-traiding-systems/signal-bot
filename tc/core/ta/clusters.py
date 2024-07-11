import pandas as pd
import numpy as np
from datetime import timedelta
from typing import Dict
# import numba
# from numba import jit
#
#


# @jit(nopython=True)
def get_clusters_by_tf(trades: pd.DataFrame, min_price: float,  max_price: float, step: float, tf_size:timedelta):
    data = trades[["price", "volume"]]
    clusters_all = {}
    min_vol = 1e10
    max_vol = 0
    for interval in list(pd.cut(data.index, np.arange(trades.index[0], trades.index[-1], tf_size)).categories):
        print(interval)
        if not pd.isnull(interval):
            chunk = data.query("@interval.left <= index < @interval.right")
            # clusters = chunk['volume'].groupby(pd.cut(chunk.price, np.arange(min_price, max_price, step))).sum()
            clusters = get_clusters(chunk, chunk.price.min(), chunk.price.max(), step)
            clusters_all[interval.left] = clusters
            min_vol = min(clusters[clusters > 0].min(), max_vol)
            max_vol = max(clusters.max(), max_vol)

    return clusters_all, (min_vol, max_vol)


def get_clusters(trades: pd.DataFrame, min_price: float, max_price: float, step: float):
    data = trades[["price", "volume"]]

    clusters = data.volume.groupby(pd.cut(data.price, np.arange(min_price, max_price, step))).sum()
    if not clusters.empty:
        min_vol = clusters[clusters > 0].min()
        max_vol = clusters.max()
        clusters_result = [(i.left, i.right, c) for i, c in clusters.items()]
    else:
        min_vol = data.volume.min()
        max_vol = data.volume.max()
        clusters_result = [[data.price.min(), data.price.max(), data.volume.sum()]]

    return clusters_result, (min_vol, max_vol)


def normalize_clusters_for_plot(clusters: pd.DataFrame) -> Dict[int, pd.DataFrame]:
        max_c = clusters.volume.max()
        clusters["v_group"] = np.round_((1 + (clusters.volume - max_c) / max_c) * 10)
        clusters["price"] = clusters[['price_from', 'price_to']].mean(axis=1)
        colors = ["#fff1f0", "#ffccc7", "#ffa39e", "#ff7875", "#ff4d4f", "#f5222d",
                  "#cf1322", "#a8071a", "#820014", "#5c0011"]
        result = {}
        for i in range(1, 11, 1):
            result[i] = clusters[clusters.v_group == i][["timestamp", "volume", "price"]]

        return result
