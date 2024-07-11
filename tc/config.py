import logging
import os
from typing import Optional, List, Dict, Any
# from core.types import Singleton
from dotenv import load_dotenv

LOG_FORMAT = f"%(asctime)s - [%(levelname)s] - %(name)s - (%(filename)s).%(funcName)s(%(lineno)d) - %(message)s"
MAX_CANDLES = 1000
ZMQ_CLUSTERS_PORT = 5555
ZMQ_ARBITRAGE_BOT_PORT = 5544
CMD_ARBITRAGE_SPREADS = "arbitrage_spreads"


class SingletonClass(object):
    instance = None

    def __new__(cls):
        if cls.instance is None:
            cls.instance = super(SingletonClass, cls).__new__(cls)
        return cls.instance


class Config(SingletonClass):
    ENV: str
    IS_DEV: bool
    LOGS_PATH: str
    DATA_PATH: str

    TRADING_DIARY_SPREEDSHEET_ID: str
    GOOGLE_SERVICE_KEY_FILE_NAME: str

    TELEGRAM_BOT_TOKEN: str
    MONGO_DB_HOST: str
    MONGO_DB_USERNAME: str
    MONGO_DB_PASSWORD: str

    TIMESCALE_DB_HOST: str
    TIMESCALE_DB_USERNAME: str
    TIMESCALE_DB_PASSWORD: str
    TIMESCALE_DB_INIT_SQL_FILE: str
    DATA_COLLECTOR_ITEMS_COUNT: str
    ORACLE_SYMBOLS_COUNT: int
    ORACLE_TFS: List[str]

    BINANCE_API_KEY: str
    BINANCE_API_SECRET: str

    MAIN_SERVER: str

    @property
    def is_dev(self):
        return self.ENV == "DEV"

    @staticmethod
    def get_timescale_db_params() -> Dict[str, Any]:
        return dict(host=Config.TIMESCALE_DB_HOST, username=Config.TIMESCALE_DB_USERNAME,
                    password=Config.TIMESCALE_DB_PASSWORD)

    @staticmethod
    def load_from_env(root_path: Optional[str] = ".", env_file_name: Optional[str] = '.env'):
        # if root_path is None:
        #     root_path = os.path.dirname(os.path.abspath(__file__))
        log_path = f'{root_path}/{env_file_name}'
        r = load_dotenv()
        logging.warning(f"Load {log_path} {r}")
        Config.ENV = os.getenv("ENVIRONMENT", "DEV")
        Config.LOGS_PATH = f'{root_path}/logs'
        Config.DATA_PATH = os.getenv("DATA_PATH")

        Config.TRADING_DIARY_SPREEDSHEET_ID = os.getenv("TRADING_DIARY_SPREEDSHEET_ID", None)
        Config.GOOGLE_SERVICE_KEY_FILE_NAME = os.getenv("GOOGLE_SERVICE_KEY_FILE_NAME")

        Config.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
        # INFLUX_DB_HOST = os.getenv("INFLUX_DB_HOST")
        # INFLUX_DB_TOKEN = os.getenv("INFLUX_DB_TOKEN")
        Config.MONGO_DB_HOST = os.getenv("MONGO_DB_HOST")
        Config.MONGO_DB_USERNAME = os.getenv("MONGO_DB_USERNAME")
        Config.MONGO_DB_PASSWORD = os.getenv("MONGO_DB_PASSWORD")

        Config.TIMESCALE_DB_HOST = os.getenv("POSTGRES_DB_HOST")
        Config.TIMESCALE_DB_USERNAME = os.getenv("POSTGRES_USER")
        Config.TIMESCALE_DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")
        Config.TIMESCALE_DB_INIT_SQL_FILE = os.getenv("TIMESCALE_DB_INIT_SQL_FILE")
        Config.DATA_COLLECTOR_ITEMS_COUNT = os.getenv("DATA_COLLECTOR_ITEMS_COUNT", 2)
        Config.ORACLE_SYMBOLS_COUNT = int(os.getenv("ORACLE_SYMBOLS_COUNT", 20))
        Config.ORACLE_TFS = os.getenv("ORACLE_TFS", "1d,4h,1h,15m").split(",")

        Config.BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
        Config.BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

        Config.MAIN_SERVER = os.getenv("MAIN_SERVER")
        Config.instance = Config

        logging.warning(Config.__dict__)
        return Config


# Config.load_from_env()
# global_config = Config
