from typing import List, Optional

from core.exchange.binance.entities import Order
from core.types import Side, OrderType, OrderStatus, SymbolStr


def get_avg_price(lst: List[Order], by_side: bool = False) -> Optional[float]:
    if len(lst) > 0:
        if by_side:
            q_price_total = sum([o.executed_quantity_by_side * o.price for o in lst if o.is_filled])
        else:
            q_price_total = sum([o.executed_quantity * o.price for o in lst if o.is_filled])

        a_total = sum([o.executed_quantity for o in lst])

        if a_total > 0:
            return q_price_total / a_total

    return None


def opposite_side(side: Side) -> Side:
    return Side.SELL if side == Side.BUY else Side.BUY


def generate_paper_order(symbol: SymbolStr, side: Side, price: float,
                         quantity: float, quantity_filled: Optional[float]):
    return Order().from_paper(raw={"symbol": symbol, "side": side.value, "origQty": quantity,
                                   "executedQty": quantity_filled, "price": price, "status": OrderStatus.FILLED,
                                   "type": OrderType.MARKET})
