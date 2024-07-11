from config import TIMESCALE_DB_INIT_SQL_FILE, TIMESCALE_DB_USERNAME, TIMESCALE_DB_PASSWORD, \
    MONGO_DB_PASSWORD,MONGO_DB_USERNAME
from tools.backtesting.performance_t import load_test_dfs
import asyncio
import asyncpg
import logging
import time
import psycopg2
from pgcopy import CopyManager
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync
from influxdb_client.client.write_api import PointSettings
from motor import motor_asyncio as momo
from urllib.parse import quote_plus

def get_influxdb():
    return InfluxDBClientAsync(
        url=f"http://127.0.0.1:8086/",
        token="9uJTwFy5rLAgSrC0-YrDc7ls-Ga9xNF8JpEq1Fcea5nzRO9QPOu6xhIH8_TlGZ_Kzuaq6V7OYnTgylCdmYJSmQ==",
        org="daseincore_org", enable_gzip=False,
    )

def get_mongo():
    uri = "mongodb://%s:%s@%s" % (quote_plus(MONGO_DB_USERNAME), quote_plus(MONGO_DB_PASSWORD), "127.0.0.1:27017")

    _mongodb_client = momo.AsyncIOMotorClient(uri)
    _mongodb_client.get_io_loop = asyncio.get_running_loop


    return _mongodb_client["candles_db"]['candles']

def get_pg_conn():
    return psycopg2.connect(
        user=TIMESCALE_DB_USERNAME,
        password=TIMESCALE_DB_PASSWORD,
        database="timescaledb",
        host="127.0.0.1",
        port="5432",
    )

async def get_asyncpg_conn():
    return await asyncpg.connect(
        user=TIMESCALE_DB_USERNAME,
        password=TIMESCALE_DB_PASSWORD,
        database="timescaledb",
        host="127.0.0.1",
        port="5432",
    )


async def prepare(conn):
    sql_file = open("/Users/dasein/dev/DaseinTradingCore/src/core/db/schema2.sql", 'r')
    sql = sql_file.read()
    await conn.execute(sql)

    return conn


async def destroy(conn):
    try:
        await conn.execute("DROP TABLE candles CASCADE;")
    except asyncpg.exceptions.UndefinedTableError as e:
        pass
    try:
        await conn.execute("DROP TABLE symbol_tf CASCADE;")
    except asyncpg.exceptions.UndefinedTableError as e:
        pass


def prepare_pg(conn):
    sql_file = open(TIMESCALE_DB_INIT_SQL_FILE, 'r')
    sql = sql_file.read()
    conn.cursor().execute(sql)

    return conn


def destroy_pg(conn):
    try:
        conn.cursor().execute("DROP TABLE candles CASCADE;")
    except Exception as e:
        pass
    try:
        conn.cursor().execute("DROP TABLE symbol_tf CASCADE;")
    except Exception as e:
        pass


symbol_tf = {}


async def get_symbol_tf_id(symbol, tf, conn):
    try:
        id = await conn.fetchval(f"INSERT INTO symbol_tf(symbol, tf) VALUES('{symbol}', '{tf}') RETURNING id")
        symbol_tf[(symbol, tf)] = id
        return id
    except asyncpg.exceptions.UniqueViolationError:
        return symbol_tf[(symbol, tf)]


def get_symbol_tf_id_pg(symbol, tf, conn):
    try:
        cursor = conn.cursor()
        cursor.execute(f"INSERT INTO symbol_tf(symbol, tf) VALUES('{symbol}', '{tf}') RETURNING id")
        id = cursor.fetchone()[0]
        symbol_tf[(symbol, tf)] = id
        return id
    except Exception as e:
        logging.error(e)
        return symbol_tf[(symbol, tf)]


def perf_pg(conn):
    for (symbol, tf), candles in load_test_dfs().items():
        candles['symbol_tf_id'] = get_symbol_tf_id_pg(symbol, tf, conn)

        tuples = [tuple(x) for x in candles.values]
        print(f"Export {symbol}, {tf} {len(candles)}")
        columns = list(candles.columns)
        mgr = CopyManager(conn, 'candles', columns)
        mgr.copy(tuples)
        conn.commit()


async def perf_asyncpg(conn, data):
    columns = ['o', 'h', 'l', 'c', 'v', 'timestamp', 'symbol', 'tf']
    for (symbol, tf), candles in data.items():
        # candles['timestamp'] = candles.index
        # candles['symbol_tf_id'] = await get_symbol_tf_id(symbol, tf, conn)
        # candles['symbol_tf'] = f'{symbol}.{tf}'
        candles['symbol'] = symbol
        candles['tf'] = tf
        tuples = [row for row in candles.itertuples(index=False, name=None)]
        # columns = list(candles.columns)
        print(f"Export {symbol}, {tf} {len(candles)}")
        # CHUNK_SIZE = 1000
        #
        # index_slices = sliced(range(len(candles)), CHUNK_SIZE)
        #
        # for index_slice in index_slices:
        #     chunk = candles.iloc[index_slice]
        #     tuples = [row for row in chunk.itertuples(index=False, name=None)]

        await conn.copy_records_to_table("candles", records=tuples, columns=columns, timeout=10)
        # statement = f"""INSERT INTO candles ({",".join(columns)})
        # VALUES($1, $2, $3, $4, $5, $6, $7)
        # ON CONFLICT (timestamp, symbol_tf) DO NOTHING;"""
        # await conn.executemany(statement, tuples)

async def perf_asyncpg_rel(conn, data):
    columns = ['o', 'h', 'l', 'c', 'v', 'timestamp', 'symbol_tf']
    for (symbol, tf), candles in data.items():
        candles['timestamp'] = candles.index
        candles['symbol_tf_id'] = await get_symbol_tf_id(symbol, tf, conn)
        # candles['symbol_tf'] = f'{symbol}.{tf}'
        tuples = [row for row in candles.itertuples(index=False, name=None)]
        # columns = list(candles.columns)
        print(f"Export {symbol}, {tf} {len(candles)}")
        # CHUNK_SIZE = 500
        #
        # index_slices = sliced(range(len(candles)), CHUNK_SIZE)
        #
        # for index_slice in index_slices:
        #     chunk = candles.iloc[index_slice]
        #     tuples = [row for row in chunk.itertuples(index=False, name=None)]

        await conn.copy_records_to_table("candles", records=tuples, columns=columns, timeout=10)
        # statement = f"""INSERT INTO candles ({",".join(columns)})
        # VALUES($1, $2, $3, $4, $5, $6, $7)
        # ON CONFLICT (timestamp, symbol_tf_id) DO NOTHING;"""
        # await conn.executemany(statement, tuples)


async def perf_influx_ins(client, data):
    for (symbol, tf), candles in data.items():
        point_settings = PointSettings(tf=tf, symbol=symbol)
        print(f"Export {symbol}, {tf} {len(candles)}")

        measurement = f'candles_'
        await client.write_api(point_settings=point_settings).write(
            bucket="dasein_bucket",
            record=candles,
            data_frame_measurement_name=measurement,
        )


async def perf_mongo_ins(client, data):
    for (symbol, tf), candles in data.items():
        print(f"Export {symbol}, {tf} {len(candles)}")

        await client.insert_many(candles.to_dict('records'))


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)

    # conn = get_pg_conn()
    # destroy_pg(conn)
    # prepare_pg(conn)
    # start = time.time()
    # perf_pg(conn)
    # end = time.time()
    # print(end - start)
    async def main():
        try:
            conn = await get_asyncpg_conn()
            await destroy(conn)
            await prepare(conn)
            await asyncio.sleep(0.5)
            data = load_test_dfs()
            start = time.time()
            await perf_asyncpg(conn, data)
            end = time.time()
            print(end - start)
        except Exception as e:
            print(e)
    # async def main():
    #     try:
    #         conn = get_influxdb()
    #         await asyncio.sleep(0.5)
    #         data = load_test_dfs()
    #         start = time.time()
    #         await perf_influx_ins(conn, data)
    #         end = time.time()
    #         print(end - start)
    #     except Exception as e:
    #         print(e)

    # async def main():
    #     try:
    #         conn = get_mongo()
    #         await asyncio.sleep(0.5)
    #         data = load_test_dfs()
    #         start = time.time()
    #         await perf_mongo_ins(conn, data)
    #         end = time.time()
    #         print(end - start)
    #     except Exception as e:
    #         print(e)

    asyncio.run(main())
