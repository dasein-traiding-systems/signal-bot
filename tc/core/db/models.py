from datetime import datetime
from typing import List, Optional, TypedDict
from uuid import UUID, uuid4

from core.types import SignalClause, SignalType, Symbol


class ExchangeNotification(TypedDict):
    # id: int = Field(alias='_id')
    # id:UUID4 Field(default_factory=uuid4())
    symbol: str
    signal_type: SignalType
    clause: SignalClause
    value: float
    triggered: bool
    trigger_after: Optional[datetime]
    group_id: Optional[UUID]


class User(TypedDict):
    telegram_id: int
    username: str
    # telegram_id: int
    first_name: Optional[str]
    last_name: Optional[str]
    binance_api_key: Optional[str]
    binance_api_secret: Optional[str]
    notifications: Optional[List[ExchangeNotification]]


# import mongox
# from pydantic import UUID4
# class ExchangeNotification(mongox.Model, db=mongo_db, collection="notifications"):
#     # id: int = Field(alias='_id')
#     # id:UUID4 Field(default_factory=uuid4())
#     symbol: str
#     signal_type: SignalType
#     clause: SignalClause
#     value: float
#     triggered: bool = False
#     group_id: Optional[UUID4]
#
#
# class User(mongox.Model, db=mongo_db, collection="users"):
#     telegram_id: int
#     username: str
#     # telegram_id: int
#     first_name: Optional[str]
#     last_name: Optional[str]
#     binance_api_key: Optional[str]
#     binance_api_secret: Optional[str]
#     notifications: Optional[List[ExchangeNotification]] = []
