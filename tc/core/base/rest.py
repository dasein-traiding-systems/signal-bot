from typing import Any, Dict, Tuple

import ujson
from aiohttp import ClientSession

from core.types import RestMethod


class AsyncRequest:
    def __init__(self, session: ClientSession):
        self.session = session

    async def request_json(
        self,
        url: str,
        method: RestMethod,
        params: Dict = None,
        json: Dict = None,
        headers: Dict = None,
        data: Dict = None,
    ) -> Tuple[Any, Any]:
        resp = await self.request(url, method, params, json, headers, data)
        content = ujson.loads(await resp.content.read())
        return content, resp

    async def request(
        self,
        url: str,
        method: RestMethod,
        params: Dict = None,
        json: Dict = None,
        headers: Dict = None,
        data: Dict = None,
    ) -> Any:
        return await self.session.request(
            method.value, url, params=params, json=json, headers=headers, data=data
        )
