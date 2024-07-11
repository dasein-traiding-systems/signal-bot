import operator
from collections import OrderedDict
from typing import Callable, Dict, List, Tuple, Union


class OrderBook(object):
    def __init__(self):
        self.bids: Dict = OrderedDict()
        self.asks: Dict = OrderedDict()

    def update_sides(
        self, bids: List[Tuple[float, float]], asks: List[Tuple[float, float]]
    ):
        self.update_asks(asks)
        self.update_bids(bids)

    def update_asks(self, asks: List[Tuple[float, float]]):
        self.asks = OrderedDict(sorted(asks, key=operator.itemgetter(0)))

    def update_bids(self, bids: List[Tuple[float, float]]):
        self.bids = OrderedDict(sorted(bids, key=operator.itemgetter(0), reverse=True))

    def _get_first_item(self, side: str) -> Tuple[float, float]:
        return next(iter(self.__dict__[side].items()))

    def top_bid_price(self) -> float:
        return self._get_first_item("bids")[0]

    def top_ask_price(self) -> float:
        return self._get_first_item("asks")[0]
