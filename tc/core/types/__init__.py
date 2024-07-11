from datetime import datetime
from enum import Enum
from typing import Dict, NewType, Optional, Tuple

Asset = NewType("Asset", str)
SymbolStr = NewType("SymbolStr", str)
Symbol = SymbolStr

Tf = NewType("Tf", str)

SymbolTf = Tuple[Symbol, Tf]


class TaLevels(Enum):
    Volume = 1
    Price = 2

# class TimeFrame(Enum):
#     _1w = "1w"
#     _1d = "1d"
#     _4h = "4h"
#     _1h = "1h"
#     _15m = "15m"
#     _5m = "5m"
#     _1m = "1m"


class RestMethod(Enum):
    POST = "POST"
    PUT = "PUT"
    GET = "GET"
    DELETE = "DELETE"


OrderId = NewType("OrderId", int)


class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"


class PositionSide(Enum):
    BUY = "BUY"
    SELL = "SELL"
    BOTH = "BOTH"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_MARKET = "STOP_MARKET"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"
    STOP_LOSS_MARKET = "STOP_LOSS_MARKET"
    STOP_LOSS_LIMIT = "STOP_LOSS_LIMIT"
    TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"
    LIQUIDATION = "LIQUIDATION"


class SideEffectType(Enum):
    NO_SIDE_EFFECT = "NO_SIDE_EFFECT"
    MARGIN_BUY = "MARGIN_BUY"
    AUTO_REPAY = "AUTO_REPAY"

# * GTC (Good-Til-Canceled) orders are effective until they are executed or canceled.
# * IOC (Immediate or Cancel) orders fills all or part of an order
#   immediately and cancels the remaining part of the order.
# * FOK (Fill or Kill) orders fills all in its entirety, otherwise, the entire order will be cancelled.
class TimeInForce(Enum):
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"


class OrderStatus(Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"
    NEW_INSURANCE = "NEW_INSURANCE"
    NEW_ADL = "NEW_ADL"


class PositionClosedBy(Enum):
    TP = "T/P"
    SL = "S/L"
    MANUAL = "MANUAL"


class SignalClause(Enum):
    UP = "UP"
    DOWN = "DOWN"
    CROSS = "CROSS"


class SignalType(Enum):
    PRICE = "PRICE"
    VOLUME = "VOLUME"


class BaseOrder(object):
    exchange = "abstract"

    def __init__(self):
        self.id: Optional[int] = None
        self.symbol: Optional[Symbol] = None
        self.client_id: Optional[int] = None
        self.side: Optional[Side] = None
        self.status: Optional[OrderStatus] = None
        self.order_type: Optional[OrderType] = None
        self.price: float = 0.0
        self.avg_price: float = 0.0
        self.stop_price: float = 0.0
        self.quantity: Optional[float] = None
        self.executed_quantity: Optional[float] = None
        self.order_time: Optional[int] = None
        self.trade_update_time: Optional[int] = None
        self.commission: float = 0.0
        self.is_isolated: Optional[bool] = None

    @property
    def cancelled(self):
        return self.status == OrderStatus.CANCELED

    @property
    def active(self):
        return self.status not in [OrderStatus.EXPIRED, OrderStatus.FILLED, OrderStatus.CANCELED]

    @property
    def is_filled(self):
        return self.status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]

    @property
    def side_sign(self):
        return -1 if self.side == Side.SELL else 1

    @property
    def quantity_by_side(self):
        return self.quantity * self.side_sign

    @property
    def executed_quantity_by_side(self):
        return self.executed_quantity * self.side_sign


class PositionImpact(Enum):
    OPEN = "OPEN"
    CLOSE = "CLOSE"


class TradeType(Enum):
    TP = "T/P"
    SL = "S/L"
    OPEN = "OPEN"


class PositionOrder(BaseOrder):
    def __init__(self):
        BaseOrder.__init__(self)
        self.position_impact: Optional[PositionImpact] = None
        self.trade_type: TradeType = TradeType.OPEN

    @staticmethod
    def from_order(order: BaseOrder):
        p_order = PositionOrder()
        p_order.__dict__.update(order.__dict__)
        return p_order


class BasePosition(object):
    exchange = "abstract"

    def __init__(self, symbol: Symbol):
        self.symbol: Optional[Symbol] = symbol
        self.amount: float = 0.0
        self.side: Optional[Side] = None
        self.entry_price: float = 0.0
        self.pnl: Optional[float] = None
        self.u_pnl: Optional[float] = None
        self.orders: Dict[int, PositionOrder] = {}
        self.trade_update_time: Optional[int] = None
        self.open_time: Optional[int] = None
        self.close_time: Optional[int] = None
        self.side_by_amount: Optional[PositionSide] = PositionSide.BOTH
        self.closed: bool = False

    @property
    def active(self):
        return self.entry_price is not None

    @property
    def amount_total(self):
        return sum(
            [
                o.executed_quantity
                for o in self.orders.values()
                if o.position_impact == PositionImpact.CLOSE and o.executed_quantity > 0
            ]
        )

    @property
    def commissions(self):
        return sum([o.commission for o in self.orders.values() if o.commission > 0])

    @property
    def abs_amount(self):
        return abs(self.amount)

    @property
    def duration(self):
        if self.open_time is None and self.close_time is None:
            return 0

        delta = datetime.utcfromtimestamp(
            self.close_time / 1000
        ) - datetime.utcfromtimestamp(self.open_time / 1000)
        return delta  # time.strftime('%H:%M:%S', time.gmtime(diff/1000))


class SingletonClass(object):
    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(SingletonClass, cls).__new__(cls)
        return cls.instance


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class ExchangeType(Enum):
    FUTURES = "FUTURES"
    SPOT = "SPOT"