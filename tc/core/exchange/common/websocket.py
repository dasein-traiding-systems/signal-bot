import asyncio
import time
import traceback
from typing import Callable, Coroutine, Dict, Optional, Any

import ujson
import websockets

from core.base import CoreBase
from core.utils.logs import setup_logger, add_traceback
from datetime import datetime
WARMUP_TIME = 15


class WebSocketBase:
    def __init__(
        self,
        name: str,
        connect: Callable[[], Coroutine],
        on_message: Callable,
        timeout: float = 0.0,
        on_reconnect: Optional[Callable[[], Coroutine]] = None,
        on_before_connect: Optional[Callable[[], Coroutine]] = None,
        on_connect: Optional[Callable[[], Coroutine]] = None,
        logger=None,
    ):
        self.connect = connect
        self.on_message = on_message
        self.name = name
        self.ws: websockets.WebSocketClientProtocol = None
        self.timeout = timeout
        # self.time = float(time.time() + WARMUP_TIME)
        self.on_reconnect = on_reconnect
        self.on_before_connect = on_before_connect
        self.on_connect = on_connect
        self.logger = setup_logger(self.name)

        CoreBase.get_loop().create_task(self.run())
        if self.timeout:
            CoreBase.get_loop().create_task(self.manage_timeout())

        # if ping_msg:
        #     loop.create_task(async_looper(ping_interval)(self.send_msg)(ujson.dumps(ping_msg)))

    # async def send_msg(self, msg: str):
    #     await self.ws.send(msg)
    @property
    def is_connected(self):
        # return self.ws is not None
        return self.ws and self.ws.open

    async def _connect(self):
        while True:
            try:
                if self.is_connected:
                    self.logger.warning(f"WS {self.name} Closing")
                    await self.ws.close()
                self.logger.warning(f"WS {self.name} Connecting")
                self.ws: websockets.WebSocketClientProtocol = await self.connect()
                self.logger.warning(f"WS {self.name} Connected")
                if self.on_connect is not None:
                    await self.on_connect()

                break
            except TimeoutError:
                self.logger.error(f"WS {self.name} timeout.")
            except Exception as ex:
                self.logger.error(f"WS {self.name} exception: {add_traceback(ex)}")
                await asyncio.sleep(1)

    async def _read_socket(self):
        try:
            while True:
                message = await self.ws.recv()
                try:
                    for line in str(message).splitlines():
                        # msg = ujson.loads(line)
                        await self.on_message(ujson.loads(line))
                except Exception as e:
                    self.logger.error(add_traceback(e))
                    # traceback.print_exc()
        except websockets.ConnectionClosedError as e:
            sleep_time = 3
            self.logger.info(
                f"WS {self.name} Connection Error: {e}. Sleep {sleep_time}..."
            )
            await asyncio.sleep(sleep_time)
        except Exception as e:
            self.logger.info(f"WS {self.name} Connection Lost at {datetime.utcnow()}")
            # logging.error(add_traceback(e))

    async def run(self):
        while True:
            if self.on_before_connect is not None:
                await self.on_before_connect()
            await self._connect()

            if self.on_reconnect is not None:
                await self.on_reconnect()

            await self._read_socket()

    async def restart_ws(self):
        await self.ws.close()
        # self.time = time.time()

    async def manage_timeout(self):
        while True:
            await asyncio.sleep(self.timeout)
            if not self.is_connected:
                return
            # now_ = time.time()
            # if now_ - self.time > self.timeout:
            #     try:
            #         self.logger.warning(
            #             f"WS {self.name}  {now_} - {self.time}({now_ - self.time}) "
            #         )
            #         # self.time = now_
            #         await self.restart_ws()
            #     except:
            #         traceback.print_exc()
