from typing import Any, List

import pandas as pd


def candles_to_data_frame(data: List[List[Any]]) -> pd.DataFrame:
    df = pd.DataFrame(data, columns=["timestamp", "o", "h", "l", "c", "v"])
    return df.set_index("timestamp")
