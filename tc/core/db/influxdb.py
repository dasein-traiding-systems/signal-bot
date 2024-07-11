import asyncio
from datetime import datetime
from typing import Optional

import pandas as pd
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync
from influxdb_client.client.influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import PointSettings

from config import Config
from core.exchange.common.mappers import symbol_to_binance
from core.types import Singleton, Symbol, Tf
from core.utils.data import candles_to_data_frame
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging
CANDLES_TABLE_NAME = "candles"
BUCKET_NAME = "dasein_bucket"
ORG_NAME = "daseincore_org"
ABSOLUTE_BEGIN_DATE = "2017-02-10T00:00:00Z"
SYNC_MODE = True

def get_time_where_condition(
        ts_from: Optional[datetime] = None, ts_to: Optional[datetime] = None
):
    if ts_from is not None and ts_to is not None:
        return f"range(start:{ts_from.strftime('%Y-%m-%dT%H:%M:%SZ')}, stop: {ts_to.strftime('%Y-%m-%dT%H:%M:%SZ')})"
    elif ts_from is not None and ts_to is None:
        return f"range(start: {ts_from.strftime('%Y-%m-%dT%H:%M:%SZ')})"
    elif ts_from is None and ts_to is not None:
        return f"range(start: {ABSOLUTE_BEGIN_DATE}, stop: {ts_to.strftime('%Y-%m-%dT%H:%M:%SZ')})"

    return f"range(start: {ABSOLUTE_BEGIN_DATE})"


class InfluxDb(object, metaclass=Singleton):
    def __init__(self, host: str, token: str):
        self.host = host
        self.token = token
        self.client: Optional[InfluxDBClientAsync, InfluxDBClient] = None
        self.init_time = datetime.utcnow()

    async def init(self):
        self.client = self._get_client()

    def _get_client(self):
        if SYNC_MODE:
            return InfluxDBClient(
                url=f"mongodb://{self.host}:8086/", token=self.token, org=ORG_NAME, enable_gzip=False,
            )

        return InfluxDBClientAsync(
            url=f"http://{self.host}:8086/", token=self.token, org=ORG_NAME, enable_gzip=False,
        )

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10),
           retry=retry_if_exception_type(asyncio.exceptions.TimeoutError))
    async def save_candles(self, symbol: Symbol, tf: Tf, candles: pd.DataFrame):
        point_settings = PointSettings(tf=tf, symbol=symbol_to_binance(symbol))
        logging.info(f"Save candles {symbol} {tf} - {len(candles)} {datetime.utcnow() - self.init_time}")
        measurement = f'{CANDLES_TABLE_NAME}.{symbol_to_binance(symbol)}.{tf}'
        self.client.write_api(point_settings=point_settings).write(
            bucket=BUCKET_NAME,
            record=candles,
            data_frame_measurement_name=measurement,
        )

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10),
           retry=retry_if_exception_type(asyncio.exceptions.TimeoutError))
    async def load_candles(
            self,
            symbol: Symbol,
            tf: Tf,
            start_time: Optional[datetime] = None,
            end_time: Optional[datetime] = None,
    ) -> pd.DataFrame:
        symbol_str = symbol_to_binance(symbol)
        timestamp_range = get_time_where_condition(start_time, end_time)
        logging.info(f"Load candles {symbol} {tf} -  {datetime.utcnow() - self.init_time}")
        measurement = f'{CANDLES_TABLE_NAME}.{symbol_to_binance(symbol)}.{tf}'

        query = f'from(bucket:"{BUCKET_NAME}")\
        |> {timestamp_range}\
        |> filter(fn:(r) => r._measurement == "{measurement}")\
        |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")\
        |> keep(columns: ["_time", "o", "h", "l", "c", "v"])'
        data = self.client.query_api().query_data_frame(query)

        if len(data) == 0:
            return candles_to_data_frame([])

        del data["result"]
        del data["table"]
        data["_time"] = data["_time"].dt.tz_localize(None)
        return data.set_index("_time")

    async def load_last_candle_timestamp(self, symbol: Symbol, tf: Tf):
        symbol_str = symbol_to_binance(symbol)
        measurement = f'{CANDLES_TABLE_NAME}.{symbol_to_binance(symbol)}.{tf}'

        query = f'from(bucket:"{BUCKET_NAME}")\
        |> range(start: 0)\
        |> filter(fn:(r) => r._measurement == "{measurement}")\
        |> filter(fn: (r) => r["_field"] == "c")\
        |> last()'

        data = self.client.query_api().query(query)
        if len(data) == 0:
            return None

        return data[0].records[0].values["_time"]


if __name__ == "__main__":
    async def main():
        logging.getLogger().setLevel(logging.INFO)
        db = InfluxDb()
        await db.init()
        item = await db.load_candles(("BNB", "USDT"), Tf("1d"))
        print(item)


    asyncio.run(main())
