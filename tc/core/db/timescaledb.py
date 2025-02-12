import asyncio
import asyncpg

from datetime import datetime
from typing import Optional, Union, Dict, Any, List
from urllib.parse import quote_plus

import pandas as pd

from config import Config
from core.base import CoreBase

from core.types import Singleton, SymbolStr, Tf, Tuple, TaLevels
from core.utils.data import candles_to_data_frame
import logging


def get_timestamp_condition(ts_from: Optional[datetime] = None, ts_to: Optional[datetime] = None) -> str:
    def format_date(date: datetime):
        return date.strftime("%Y-%m-%d %H:%M:%S")

    if ts_from is not None and ts_to is not None:
        return f" timestamp >= '{format_date(ts_from)}' AND timestamp < '{format_date(ts_to)}' "
    elif ts_from is not None and ts_to is None:
        return f" timestamp >= '{format_date(ts_from)}' "
    elif ts_from is None and ts_to is not None:
        return f" timestamp < '{format_date(ts_to)}' "

    return " 1=1"


class TimesScaleDb(object, metaclass=Singleton):
    def __init__(self, host: str, username: str,
                 password: str, use_pool=False):
        self.host = host
        self.username = username
        self.password = password
        self.uri = "postgres://%s:%s@%s/timescaledb" % (quote_plus(username), quote_plus(password), host)
        self.conn: Optional[Union[asyncpg.connection.Connection, asyncpg.pool.Pool]] = None
        self.init_time = datetime.utcnow()
        self.symbol_tf: Dict[Tuple[SymbolStr, Tf], int] = {}
        self.use_pool = use_pool

    async def init(self, simple=False):
        if self.conn is None:
            logging.info(f"Init DB at {self.host}")
            params = dict(user=self.username,
                          password=self.password,
                          database="timescaledb",
                          host=self.host,
                          port="5432")
            if self.use_pool:
                self.conn = await asyncpg.create_pool(**params)
            else:
                self.conn = await asyncpg.connect(**params)

            if not simple:
                # await self.init_migration()
                await self.init_symbols()

    async def init_migration(self):
        try:
            sql_file = open(Config.TIMESCALE_DB_INIT_SQL_FILE, 'r')
            sql = sql_file.read()
            await self.conn.execute(sql)
        except Exception as e:
            logging.warning(e)

    async def fetch_as_dataframe(self, sql: str, *args):
        if self.use_pool:
            async with self.conn.acquire() as conn:
                stmt = await conn.prepare(sql)
                columns = [a.name for a in stmt.get_attributes()]
                data = await stmt.fetch(*args)
        else:
            stmt = await self.conn.prepare(sql)
            columns = [a.name for a in stmt.get_attributes()]
            data = await stmt.fetch(*args)
        return pd.DataFrame(data, columns=columns)

    async def add_symbol(self, symbol: SymbolStr, tf: Tf):
        try:
            id = await self.conn.fetchval(f"INSERT INTO symbol_tf(symbol, tf) VALUES('{symbol}', '{tf}') RETURNING id")
            logging.warning(f"{symbol}, {tf} ADDED id: {id}")

            self.symbol_tf[(symbol, tf)] = id
            return id
        except asyncpg.exceptions.UniqueViolationError:
            logging.warning(f"{symbol}, {tf} - already exist!")
            return self.symbol_tf[(symbol, tf)]

    async def add_symbol_status(self, symbol: SymbolStr, last_sync: datetime, last_volume: float, active: bool):
        symbol_tf_id = await self.get_symbol_tf_id(symbol)
        statement = f"""INSERT INTO symbol_status (symbol_tf_id, last_sync, last_volume, active) 
        VALUES($1, $2, $3, $4) 
        ON CONFLICT (symbol_tf_id) DO UPDATE SET last_sync=$2, last_volume=$3, active=$4;"""

        await self.conn.execute(statement, symbol_tf_id, last_sync, last_volume, active)

    async def update_symbol_status_one_value(self, symbol: SymbolStr, last_sync: Optional[datetime] = None,
                                             last_volume: Optional[float] = None, active: Optional[bool] = None,
                                             cluster_size: Optional[float] = None):
        symbol_tf_id = await self.get_symbol_tf_id(symbol)
        column = ""
        value: Optional[Union[float, datetime, bool]] = None
        if last_volume is not None:
            column = "last_volume"
            value = last_volume
        elif last_sync is not None:
            column = "last_sync"
            value = last_sync
        elif active is not None:
            column = "active"
            value = active
        elif cluster_size is not None:
            column = "cluster_size"
            value = cluster_size

        await self.conn.execute(
            f'UPDATE symbol_status SET {column}=$2 WHERE symbol_tf_id=$1', symbol_tf_id, value)

    async def get_symbol_status(self, active: Optional[bool] = None,
                                symbol: Optional[SymbolStr] = None) -> Union[Dict[str, Any],
                                                                             List[Dict[str, Any]]]:
        statement = f"""SELECT symbol_status.symbol_tf_id, symbol_tf.symbol, symbol_status.last_sync, 
        symbol_status.last_volume, symbol_status.active, symbol_status.cluster_size
        FROM symbol_status JOIN symbol_tf ON symbol_status.symbol_tf_id = symbol_tf.id """
        if symbol is not None:
            statement += f" WHERE symbol='{symbol}' and tf='1d'"
            return await self.conn.fetchrow(statement)
        elif active is not None:
            statement += f" WHERE active={str(active).lower()}"
            return await self.conn.fetch(statement)

    async def get_symbol_tf_id(self, symbol: SymbolStr, tf: Optional[Tf] = '1d'):
        if (symbol, tf) not in self.symbol_tf.keys():
            symbol_tf_id = await self.add_symbol(symbol, tf)
        else:
            symbol_tf_id = self.symbol_tf[(symbol, tf)]

        return symbol_tf_id

    async def init_symbols(self):
        self.symbol_tf = {(SymbolStr(i['symbol']), Tf(i['tf'])): i['id']
                          for i in await self.conn.fetch(f'SELECT * from symbol_tf')}

        return self.symbol_tf

    async def save_candles(self, symbol: SymbolStr, tf: Tf, candles: pd.DataFrame):
        logging.info(f"Save candles {symbol} {tf} - {len(candles)} {datetime.utcnow() - self.init_time}")
        candles['timestamp'] = candles.index
        candles['symbol_tf_id'] = await self.get_symbol_tf_id(symbol, tf)

        tuples = [tuple(x) for x in candles.values]
        columns = list(candles.columns)
        candles.drop(['timestamp', 'symbol_tf_id'], axis=1)
        try:
            # INSERT ON CONFLICT DO UPDATE
            # await self.conn.execute("CREATE TEMPORARY TABLE _candles (timestamp TIMESTAMP,"
            #                         "symbol_tf_id INTEGER,"
            #                         "o   DOUBLE PRECISION,"
            #                         "h   DOUBLE PRECISION,"
            #                         "l   DOUBLE PRECISION,"
            #                         "c   DOUBLE PRECISION,"
            #                         "v   DOUBLE PRECISION)")
            try:
                await self.conn.copy_records_to_table("candles", records=tuples, columns=columns,
                                                      timeout=10)
            except asyncpg.exceptions.UniqueViolationError as e:
                statement = f"""INSERT INTO candles ({",".join(columns)}) 
                VALUES($1, $2, $3, $4, $5, $6, $7) 
                ON CONFLICT (timestamp, symbol_tf_id) DO NOTHING;"""
                await self.conn.executemany(statement, tuples)

            # await conn.execute('''CREATE TEMPORARY TABLE _data(
            #     timestamp TIMESTAMP, value NUMERIC
            # )''')
            # await conn.copy_records_to_table('_data', records=values)
            # await conn.execute('''
            #     INSERT INTO {table}(timestamp, value)
            #     SELECT * FROM _data
            #     ON CONFLICT (timestamp)
            #     DO UPDATE SET value=EXCLUDED.value
            # '''.format(table=table))
        except asyncpg.exceptions.UniqueViolationError as e:
            logging.warning(f"save candles error {e}")

    async def load_candles(
            self,
            symbol: SymbolStr,
            tf: Tf,
            start_time: Optional[datetime] = None,
            end_time: Optional[datetime] = None,
    ) -> pd.DataFrame:
        logging.info(f"Load candles {symbol} {tf} -  {datetime.utcnow() - self.init_time}")
        if (symbol, tf) not in self.symbol_tf.keys():
            return candles_to_data_frame([])

        symbol_tf_id = self.symbol_tf[(symbol, tf)]

        statement = f"SELECT * FROM candles WHERE symbol_tf_id = {symbol_tf_id} AND " \
                    f"{get_timestamp_condition(start_time, end_time)} " \
                    f"ORDER BY timestamp ASC"

        # logging.info(f"Load candles {symbol} {tf} -  {statement}")

        df = await self.fetch_as_dataframe(statement)

        return df.set_index("timestamp")

    async def load_last_candle_timestamp(self, symbol: SymbolStr, tf: Tf):
        if (symbol, tf) not in self.symbol_tf.keys():
            return None

        symbol_tf_id = self.symbol_tf[(symbol, tf)]
        result = await self.conn.fetchval(f"SELECT timestamp FROM CANDLES where symbol_tf_id = {symbol_tf_id} ")
        return result

    async def add_trade(self, symbol: SymbolStr, price: float, volume: float, is_buyer: bool, timestamp: datetime):
        symbol_tf_id = await self.get_symbol_tf_id(symbol)

        await self.conn.execute("INSERT INTO trades (symbol_tf_id, price, volume, is_buyer, timestamp) "
                                "VALUES ($1, $2, $3, $4, $5) ON CONFLICT (timestamp, symbol_tf_id) DO NOTHING;",
                                symbol_tf_id, price, volume, is_buyer, timestamp)

    async def load_trades(
            self,
            symbol: SymbolStr,
            start_time: Optional[datetime] = None,
            end_time: Optional[datetime] = None,
    ) -> pd.DataFrame:
        logging.info(f"Load trades {symbol} - {start_time} - {end_time} | {datetime.utcnow() - self.init_time}")
        symbol_tf_id = await self.get_symbol_tf_id(symbol)

        df = await self.fetch_as_dataframe(f"SELECT * FROM trades WHERE symbol_tf_id = {symbol_tf_id} AND "
                                           f"{get_timestamp_condition(start_time, end_time)}")

        return df.set_index("timestamp")

    async def save_clusters(self, symbol_tf_id: int, timestamp: datetime, step: float, clusters: pd.DataFrame):
        # logging.info(f"Save clusters {symbol_tf_id} - {timestamp}")

        clusters['timestamp'] = timestamp
        clusters['step'] = step
        clusters['symbol_tf_id'] = symbol_tf_id

        tuples = [tuple(x) for x in clusters.values]
        columns = list(clusters.columns)
        await self.conn.copy_records_to_table("clusters", records=tuples, columns=columns, timeout=10)

    async def load_clusters(self, symbol: SymbolStr, tf: Optional[Tf] = "15m",
                            start_time: Optional[datetime] = None, end_time: Optional[datetime] = None):

        statement = f"""SELECT * FROM clusters JOIN symbol_tf ON clusters.symbol_tf_id = symbol_tf.id 
                    WHERE symbol='{symbol}' and tf='{tf}' AND {get_timestamp_condition(start_time, end_time)}"""

        df = await self.fetch_as_dataframe(statement)
        return df

    async def save_levels(self, symbol_tf_id: int, timestamp: datetime, level_type: TaLevels, level_value: float):
        # logging.info(f"Save levels {symbol_tf_id} - {timestamp} {level_type} = {level_value}")
        delete_sql = f"DELETE FROM levels WHERE symbol_tf_id={symbol_tf_id} AND " \
                     f"level_type={level_type.value}"
        insert_sql = "INSERT INTO levels (symbol_tf_id, level_type, level_value, timestamp) " \
                     "VALUES ($1, $2, $3, $4);"
        if self.use_pool:
            async with self.conn.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(delete_sql)
                    await conn.execute(insert_sql, symbol_tf_id, level_type.value, level_value, timestamp)
        else:
            async with self.conn.transaction():
                await self.conn.execute(delete_sql)
                await self.conn.execute(insert_sql, symbol_tf_id, level_type.value, level_value, timestamp)

    async def load_levels(self, symbol: Union[SymbolStr, List[SymbolStr]], tf: Union[Tf, List[Tf]],
                          level_type: Optional[TaLevels] = None):
        statement = f"""SELECT * FROM levels JOIN symbol_tf ON levels.symbol_tf_id = symbol_tf.id 
                    WHERE """
        if type(symbol) is SymbolStr:
            statement += f" symbol='{symbol}' "
        else:
            symbols_str = [f"'{s}'" for s in symbol]
            statement += f" symbol IN ({','.join(symbols_str)}) "

        if type(tf) is Tf:
            statement += f" and tf='{tf}' "
        else:
            tf_str = [f"'{s}'" for s in tf]
            statement += f" and tf IN ({','.join(tf_str)}) "

        if level_type is not None:
            statement += f" and level_type={level_type.value} "

            # statement = f"""SELECT * FROM levels JOIN symbol_tf ON clusters.symbol_tf_id = symbol_tf.id
        #             WHERE symbol='{symbol}' and tf='{tf}' AND level_type={level_type.value}"""
        items = await self.conn.fetch(statement)
        return items

    async def save_arbitrage_deltas(self, timestamp: datetime, data: pd.DataFrame):

        data['timestamp'] = timestamp
        # clusters['symbol_tf_id'] = symbol_tf_id

        tuples = [tuple(x) for x in data.values]
        columns = list(data.columns)
        await self.conn.copy_records_to_table("arbitrage_delta", records=tuples, columns=columns, timeout=10)

    async def load_last_arbitrage_deltas(self):
        statement = f"""select distinct on(s.symbol) *
                    from arbitrage_delta as a join symbol_tf as s on s.id = a.symbol_tf_id 
                    order by s.symbol, "timestamp" desc; """

        df = await self.fetch_as_dataframe(statement)
        df.set_index("symbol", inplace=True)

        return df

    async def load_last_arbitrage_deltas_stats(self, start_time: Optional[datetime] = None,
                                               end_time: Optional[datetime] = None):
        statement = f"""select s.symbol, avg(a.delta) as avg_delta, avg(a.delta_perc) as avg_delta_perc,
                    max(a.delta) as max_delta, max(a.delta_perc) as max_delta_perc,
                    min(a.delta) as min_delta, min(a.delta_perc) as min_delta_perc
                    from arbitrage_delta as a join symbol_tf as s on s.id = a.symbol_tf_id 
                    WHERE {get_timestamp_condition(start_time, end_time)} 
                    GROUP BY s.symbol;"""

        df = await self.fetch_as_dataframe(statement)
        df.set_index("symbol", inplace=True)

        return df

    async def load_arbitrage_deltas(self, symbol: Optional[SymbolStr] = None,
                                    start_time: Optional[datetime] = None,
                                    end_time: Optional[datetime] = None):
        symbol_cond = ""
        if symbol is not None:
            symbol_cond = f"AND symbol='{symbol}' "

        statement = f"""select timestamp, s.symbol, a.delta_perc
                        from arbitrage_delta as a join symbol_tf as s on s.id = a.symbol_tf_id 
                    WHERE {get_timestamp_condition(start_time, end_time)} {symbol_cond}
                    group by timestamp, s.symbol, a.delta_perc
                    order by timestamp;"""

        df = await self.fetch_as_dataframe(statement)
        # df.set_index("symbol", inplace=True)

        return df


if __name__ == "__main__":
    async def main():
        logging.getLogger().setLevel(logging.INFO)
        db = TimesScaleDb()
        await db.init()
        print(await db.load_clusters("ETHUSDT", "15m"))
        # print(db.symbol_tf.keys())
        # await db.add_symbol("ETHUSDT", "1d")
        # await db.add_symbol("BTCUSDT", "1h")
        # print(await db.load_trades("BTCUSDT"))
        # print(await db.load_last_candle_timestamp("BTCUSDT", "1d"))
        # candles = await db.load_candles("BTCUSDT", "1d", start_time=datetime.utcnow() - timedelta(days=60))
        # print(candles)
        # item = await db.load_candles(("BNB", "USDT"), Tf("1d"))
        # print(item)


    asyncio.run(main())
