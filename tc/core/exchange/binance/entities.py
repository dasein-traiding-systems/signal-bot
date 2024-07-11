from typing import Any, Dict, List, Optional

from core.exchange.common.mappers import binance_to_symbol, symbol_to_binance
from core.types import (
    BaseOrder,
    BasePosition,
    OrderStatus,
    OrderType,
    PositionImpact,
    PositionOrder,
    PositionSide,
    Side,
    Symbol,
    TradeType,
    OrderId
)
from core.utils.utils import human_price


def get_avg_price_by_orders(lst: List[BaseOrder]) -> float:
    if len(lst) == 0:
        return 0.0

    q_price_total = sum([o.executed_quantity * o.price for o in lst if o.is_filled])
    a_total = sum([o.executed_quantity for o in lst])

    if a_total == 0:
        return sum([o.price for o in lst]) / len(lst)

    return q_price_total / a_total


def opposite_side(side: Side) -> Side:
    return Side.BUY if side == Side.SELL else Side.SELL


class Order(BaseOrder):
    exchange = "binance"

    def __init__(self):
        BaseOrder.__init__(self)
        self.raw: Dict[str, Any] = {}
        self.fills: Optional[List[Any]] = None

    def from_ws(self, raw: Dict, trade_update_time: Optional[int] = 0):
        self.id = OrderId(int(raw["i"]))
        self.client_id = raw["c"]
        self.symbol = binance_to_symbol(raw["s"])
        self.side = Side(raw["S"])
        self.status = OrderStatus(raw["X"])
        self.order_type = OrderType(raw["o"])
        self.price = float(raw["p"])
        self.avg_price = float(raw.get("ap", 0))
        self.stop_price = float(raw.get("sp", 0))
        self.commission = float(raw.get("n", 0))

        if self.order_type in [OrderType.STOP_MARKET, OrderType.TAKE_PROFIT_MARKET]:
            self.price = self.stop_price

        if self.avg_price == 0:
            self.avg_price = self.price

        self.quantity = float(raw["q"])
        self.executed_quantity = float(raw["z"])
        self.order_time = int(raw["T"])
        self.trade_update_time = int(trade_update_time)
        self.raw = raw

        return self

    @property
    def is_margin(self):
        return self.is_isolated is not None

    def from_paper(self, raw: Dict):
        self.symbol = binance_to_symbol(raw["symbol"])
        self.side = Side(raw["side"])
        self.status = OrderStatus(raw["status"])
        self.order_type = OrderType(raw["type"])
        self.price = float(raw["price"])
        self.quantity = float(raw['origQty'])
        self.executed_quantity = float(raw['executedQty'])

        return self

    def from_rest(self, raw: Dict, trade_update_time: Optional[int] = 0):
        self.id = OrderId(raw["orderId"])
        self.client_id = raw["clientOrderId"]
        self.symbol = binance_to_symbol(raw["symbol"])
        self.side = Side(raw["side"])
        self.status = OrderStatus(raw["status"])
        self.order_type = OrderType(raw["type"])
        self.price = float(raw["price"])
        self.avg_price = float(raw.get("avgPrice", 0))
        self.stop_price = float(raw.get("stopPrice", 0))
        self.commission = 0.0
        self.is_isolated: Optional[bool] = raw.get("isIsolated", None)

        if self.status == OrderStatus.FILLED and\
                self.order_type in [OrderType.STOP_MARKET, OrderType.TAKE_PROFIT_MARKET, OrderType.STOP_LOSS_MARKET]:
            self.price = float(raw['cummulativeQuoteQty']) / float(raw['executedQty'])

        #     self.price = self.stop_price
        #
        # if self.avg_price is None:
        #     self.avg_price = self.price

        self.quantity = float(raw['origQty'])
        self.executed_quantity = float(raw['executedQty'])
        self.order_time = int(raw.get('transactTime', raw.get('updateTime', 0)))
        self.trade_update_time = int(trade_update_time)
        self.fills = fills = raw.get("fills", None)

        if self.price == 0:  # MARKET ORDER FUTURES
            self.price = self.avg_price

        if fills is not None and len(fills) > 0: # CALC FILLS BASED PRICE
            self.commission = sum([float(o['commission']) for o in fills])
            q_price_total = sum([float(o['qty']) * float(o['price']) for o in fills])
            a_total = sum([float(o['qty']) for o in fills])

            self.price = q_price_total / a_total

        self.raw = raw

        return self

    def __str__(self):
        is_market = self.order_type in [OrderType.STOP_MARKET, OrderType.MARKET, OrderType.TAKE_PROFIT_MARKET]
        is_filled = self.status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]
        return (
            "{status} {side}_{symb}@{price}{stop} ({f_amount}/{amount}) id:{id}".format(
                price="" if self.price == 0 else human_price(self.price),
                id=self.id,
                exchange=self.exchange,
                side=self.side.value,
                amount=self.quantity,
                status=self.status.value,
                symb=symbol_to_binance(self.symbol),
                stop=f"(stop:{self.stop_price})" if self.stop_price > 0 else "",
                f_amount=self.executed_quantity,
            )
        )


class Position(BasePosition):
    exchange = "binance"

    def __init__(self, symbol: Symbol):
        BasePosition.__init__(self, symbol)
        self.amount_before: float = 0
        self.last_order: Optional[Order] = None
        self.raw: Dict[str, Any] = {}

    def __str__(self):
        return "POSITION {side} {symb} - {price} ({amount}) | uPNL={upnl} PNL={pnl}".format(
            price=human_price(self.entry_price),
            side=self.side_by_amount.value,
            amount=self.amount,
            symb=symbol_to_binance(self.symbol),
            upnl=self.u_pnl,
            pnl=self.pnl,
        )

    def update_from_ws(self, raw: Dict, trade_update_time: Optional[int] = None):
        self.amount_before = self.amount
        self.amount = float(raw["pa"])
        self.pnl = float(raw["cr"])
        self.u_pnl = float(raw["up"])
        self.side = PositionSide(raw["ps"])
        self.trade_update_time = int(trade_update_time)

        if self.open_time is None:
            self.open_time = self.trade_update_time
            self.symbol = binance_to_symbol(raw["s"])

        if self.amount == 0:
            self.close_time = self.trade_update_time
            # self.side_by_amount = PositionSide.BOTH
        else:
            self.entry_price = float(raw["ep"])
            self.side_by_amount = Side(
                (PositionSide.SELL if self.amount < 0 else PositionSide.BUY).value
            )
        self.raw = raw

        return self

    def update_order(self, order: Order):
        # set side before position is open
        if self.side == PositionSide.BOTH:
            self.side = PositionSide(order.side.value)

        p_order = PositionOrder.from_order(order)

        if self.entry_price == p_order.price:
            p_order.trade_type = TradeType.OPEN
        else:
            if p_order.price > self.entry_price:
                p_order.trade_type = (
                    TradeType.TP if self.side == PositionSide.SELL else TradeType.SL
                )
            else:
                p_order.trade_type = (
                    TradeType.SL if self.side == PositionSide.BUY else TradeType.TP
                )

        if order.trade_update_time == self.trade_update_time:
            increase_position = abs(self.amount_before) < abs(self.amount)
            p_order.position_impact = (
                PositionImpact.OPEN if increase_position else PositionImpact.CLOSE
            )

        self.orders[order.id] = p_order

        open_orders = [
            o for o in self.orders.values() if o.position_impact == PositionImpact.OPEN
        ]

        # Clean up canceled and expired if position not opened
        if len(open_orders) == 0:
            self.orders = {
                id: o
                for id, o in self.orders.items()
                if o.status not in [OrderStatus.EXPIRED, OrderStatus.CANCELED]
            }

        if abs(self.amount_before) > 0 and self.amount == 0:
            last_fill_orders = [
                o
                for o in self.orders.values()
                if o.trade_update_time == self.trade_update_time
                and o.status == OrderStatus.FILLED
            ]
            self.closed = len(last_fill_orders) > 0

        return self

    @property
    def close_price(self):
        orders = [
            o for o in self.orders.values() if o.position_impact == PositionImpact.CLOSE
        ]
        price = get_avg_price_by_orders(orders)
        return price

    def get_tp_price(self):
        orders = [o for o in self.orders.values() if o.trade_type == TradeType.TP]
        price = get_avg_price_by_orders(orders)
        return price

    def get_sl_price(self):
        orders = [o for o in self.orders.values() if o.trade_type == TradeType.SL]
        price = get_avg_price_by_orders(orders)
        return price
