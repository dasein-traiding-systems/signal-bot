import asyncio
from typing import Optional
from aiohttp import ClientSession, ClientTimeout

from core.base.rest import AsyncRequest


# if not config.IS_DEV:
#     import uvloop
#     asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


# asyncio.set_event_loop_policy(uvloop.EventLoopPolicy()) #DISABLED TMP
# loop = asyncio.get_event_loop()
# session = ClientSession(loop=loop)
# request = AsyncRequest(session)


class CoreBase:
    session: Optional[ClientSession] = None
    loop: Optional[asyncio.AbstractEventLoop] = None
    request: Optional[AsyncRequest] = None

    @classmethod
    def get_loop(cls) -> asyncio.AbstractEventLoop:
        if cls.loop is None:
            cls.loop = asyncio.get_event_loop()

        return cls.loop

    @classmethod
    def get_request(cls) -> AsyncRequest:
        if cls.request is None:
            cls.loop = cls.get_loop()
            # asyncio.set_event_loop_policy(uvloop.EventLoopPolicy()) #DISABLED TMP
            timeout = ClientTimeout(total=600)

            cls.session = ClientSession(loop=cls.loop, timeout=timeout)
            cls.request = AsyncRequest(cls.session)

        return cls.request

    @classmethod
    async def close(cls):
        if cls.session is not None:
            await cls.session.close()

        if cls.loop is not None:
            cls.loop.close()


