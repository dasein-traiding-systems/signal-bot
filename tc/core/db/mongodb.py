import asyncio
from typing import List, Optional
from urllib.parse import quote_plus

from motor import motor_asyncio as momo

from config import Config
from core.db.models import User
from core.types import Singleton

DB_NAME = "trading_sys_db"


class MongoDb(object, metaclass=Singleton):
    def __init__(
        self,
        config: Config
    ):

        host = config.MONGO_DB_HOST
        username = config.MONGO_DB_USERNAME
        password = config.MONGO_DB_PASSWORD

        uri = "mongodb://%s:%s@%s" % (quote_plus(username), quote_plus(password), host)

        self._mongodb_client = momo.AsyncIOMotorClient(uri)
        self._mongodb_client.get_io_loop = asyncio.get_running_loop

        self._mongo_db: momo.core.AgnosticDatabase = self._mongodb_client[
            DB_NAME
        ]  # .get_database(DB_NAME)
        self._users: momo.core.AgnosticCollection = self._mongo_db["users"]

    async def add_user(self, user: User):
        await self._users.update_one(
            filter={
                "telegram_id": user["telegram_id"],
            },
            update={"$setOnInsert": user},
            upsert=True,
        )

    async def list_users(self) -> List[User]:
        users = await self._users.find().to_list(length=None)
        return users


