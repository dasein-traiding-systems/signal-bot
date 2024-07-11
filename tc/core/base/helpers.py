import asyncio
import traceback
from typing import Any, Callable, Coroutine, Dict, List, Tuple, TypeVar, Union

from . import loop

# _RespType = TypeVar('T')
# _ReqType = TypeVar('T')


def async_looper(sleep_: Union[float, int]):
    def decorator(fn: Callable[[Any], Coroutine]):
        async def decorated(*args: Any):
            while True:
                try:
                    loop.create_task(fn(*args))
                except:
                    traceback.print_exc()
                await asyncio.sleep(sleep_)

        return decorated

    return decorator
