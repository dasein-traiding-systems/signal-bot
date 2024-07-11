import logging
from typing import Any, Dict
from core.utils.logs import add_traceback

def get_filter_value(
    data: Dict, filter_type: str, name: str, name_of_filter="filterType", default=None
):
    try:
        return [item[name] for item in data if item[name_of_filter] == filter_type][0]
    except IndexError as e:
        logging.warning(add_traceback(e))
        return default
