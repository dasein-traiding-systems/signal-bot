from datetime import datetime


def human_price(price: float) -> str:
    return "{:.8f}".format(price) if price is not None and price < 0.1 else price


def string_to_date(str_date: str) -> datetime:
    return datetime.strptime(str_date, "%Y-%m-%d %H:%M:%S")


def get_cluster_size(price: float):
    ratios = {10000: 10, 1000: 2, 100: 1, 10: 0.2, 1: 0.025, 0.1: 0.0025, 0.01: 0.0002}
    for k, v in ratios.items():
        if price > k:
            return v

    return 0.00001
