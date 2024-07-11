from typing import List, Any, Dict, Optional, Callable


def dict_any_value(
    keys: List[Any], dict: Dict[Any, Any], default: Optional[Any] = None
) -> Any:
    for key in keys:
        if key in dict.keys():
            return dict[key]

    return default


def dict_pick_only(dict: Dict[Any, Any], keys: List[Any]):
    return {k: v for k, v in dict.items() if k in keys}


def dict_values_as_lambda(dict: Dict[Any, Any], func_:Callable[[Any], Any] ):
    return {k: func_(v) for k, v in dict.items()}


def dict_pick_exclude(dict: Dict[Any, Any], keys: List[Any]):
    return {k: v for k, v in dict.items() if k not in keys}


def add_item_to_dict(key: Any, dict: Dict[Any, List[Any]], item: Any):
    if key not in dict:
        dict[key] = []

    dict[key] = item


def append_item_to_dict_list(key: Any, dict: Dict[Any, List[Any]], item: Any):
    if key not in dict:
        dict[key] = []

    dict[key].append(item)