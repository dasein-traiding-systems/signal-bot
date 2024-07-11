from datetime import datetime
from typing import Optional, Union, Dict, Any, List, TypeVar
from urllib.parse import quote_plus
import logging
import pandas as pd
import asyncio
from config import Config

from core.types import Singleton, SymbolStr, Tf, Tuple, TaLevels
from core.utils.data import candles_to_data_frame
from core.db import TimesScaleDb
from core.base import CoreBase


class DataProvider(object):
    def __init__(self):
        pass

    async def save_candles(self, symbol: SymbolStr, tf: Tf, candles: pd.DataFrame):
        logging.warning(f"save_candles - not implemented")

    async def load_candles(
            self,
            symbol: SymbolStr,
            tf: Tf,
            start_time: Optional[datetime] = None,
            end_time: Optional[datetime] = None,
    ) -> pd.DataFrame:
        logging.warning(f"load_candles - not implemented")
        return pd.DataFrame()

    async def init(self):
        pass


# TDataProvider = TypeVar("TDataProvider", bound="DataProvider")


class TimescaleDataProvider(DataProvider):
    def __init__(self, config: Optional[Config] = None, db: Optional[TimesScaleDb] = None):
        super().__init__()
        self.db: Optional[TimesScaleDb] = db or TimesScaleDb(**config.get_timescale_db_params())

    async def save_candles(self, symbol: SymbolStr, tf: Tf, candles: pd.DataFrame):
        await self.db.save_candles(symbol, tf, candles)

    async def load_candles(
            self,
            symbol: SymbolStr,
            tf: Tf,
            start_time: Optional[datetime] = None,
            end_time: Optional[datetime] = None,
    ) -> pd.DataFrame:
        return await self.db.load_candles(symbol, tf, start_time, end_time)

    async def init(self):
        await self.db.init()

# async def create_timescale_db_data_provider(host: str, username: str, password: str):
#     db_provider = TimescaleDataProvider(host, username, password)
#     await db_provider.db.init()
#     return db_provider
