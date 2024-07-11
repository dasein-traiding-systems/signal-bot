import os

from config import DATA_PATH
from core.ta.ta import load_data


def get_test_filenames(length=10):
    return os.listdir(DATA_PATH)[:length]


def get_symbol_tf(file_path):
    file_name = os.path.basename(file_path)
    name = file_name.split(".")[0]
    symbol, tf = name.split("_")
    symbol = symbol.replace("-", "")

    return symbol, tf


def load_test_dfs(length=25):
    result = {}
    for file_name in get_test_filenames(length):
        symbol, tf = get_symbol_tf(file_name)

        result[(symbol, tf)] = load_data(f"{DATA_PATH}/{file_name}")

    return result
