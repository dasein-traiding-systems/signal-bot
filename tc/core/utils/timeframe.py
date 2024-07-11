from datetime import datetime, timedelta

from config import MAX_CANDLES


def tf_size_minutes(tf: str) -> int:
    if tf[-1] == "m":
        return int(tf[:-1])
    if tf[-1] == "h":
        return int(tf[:-1]) * 60
    if tf[-1] == "d":
        return int(tf[:-1]) * 60 * 24

    raise KeyError


def round_time_to_tf(date, tf) -> datetime:
    result = round_time(date, tf)
    letter = tf[-1]
    if len(tf) == 1 or int(tf[:-1]) == 1:
        return result

    num = int(tf[:-1])

    if letter == "m":
        full_num, _ = divmod(result.minute, num)
        return result.replace(minute=full_num * num)
    elif letter == "h":
        full_num, _ = divmod(result.hour, num)
        return result.replace(hour=full_num * num)
    elif letter == "d":
        return round_time(date, tf)

    raise Exception(f"Invalid time frame {tf} with {date}")


def round_time(date, tf="1m") -> datetime:
    result = date.replace(second=0, microsecond=0)
    if tf[-1] in ["h", "d"]:
        result = result.replace(minute=0)
    if tf[-1] in ["d"]:
        result = result.replace(hour=0)

    return result


def get_time_shift(to_time: datetime, candle_size_minutes: int) -> datetime:
    return to_time - timedelta(minutes=MAX_CANDLES * candle_size_minutes)