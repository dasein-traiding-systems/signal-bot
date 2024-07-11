import asyncio
import hashlib
import hmac
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import websockets
from websockets import WebSocketClientProtocol

from core.base import CoreBase
from core.utils.dict_ import dict_pick_exclude, dict_values_as_lambda
from core.exchange.binance.public import PublicBinance
from core.exchange.binance.entities import Order
from core.exchange.binance.public import BASE_URI, MARGIN_URI
from core.exchange.common.exchange import PrivateExchange
from core.exchange.common.mappers import binance_to_symbol, symbol_to_binance
from core.exchange.common.websocket import WebSocketBase
from core.types import RestMethod, Symbol, OrderType, Side, SymbolStr, TimeInForce, SideEffectType, ExchangeType
from core.utils.logs import setup_logger, add_traceback
from config import Config
import logging
from copy import copy
WSS_URL = "wss://stream.binance.com:9443/ws/"
MAX_ALL_ORDERS = 100


class PrivateBinance(PrivateExchange):
    exchange = "binance"
    base_uri = BASE_URI
    base_margin_uri = MARGIN_URI
    wss_url = WSS_URL
    exchange_type = ExchangeType.SPOT

    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self.listen_key = None
        self.headers = {"X-MBX-APIKEY": self.api_key}
        self.websocket_name = "binance_private"
        self.wsb: Optional[WebSocketBase] = None
        self.public = PublicBinance()
        # self.public_futures = PublicFuturesBinance()
        self.logger = setup_logger(self.websocket_name)

    async def async_init(self, with_public: bool = True):
        self.logger.info(f"{self.websocket_name} init...")
        if with_public:
            await self.public.async_init()

        self.wsb = WebSocketBase(
            self.websocket_name,
            self.ws_private_connect,
            self.ws_on_private_message,
            timeout=0,
            on_before_connect=self.before_connect_private_streams,
        )

        await asyncio.sleep(0)

    async def private_request_url(
            self,
            url: str,
            method: RestMethod,
            rate_limited: bool = False,
            params: Dict = {},
            is_margin: bool = False
    ) -> Tuple[Optional[Dict], Any]:
        if not params:
            params = {}
        params["timestamp"] = int(time.time() * 1000)
        payload = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        url_private = f"{url}?{payload}&signature={signature}"

        return await self.public.request_url(
            url=url_private, method=method, params={}, headers=self.headers,
            base_uri=self.base_margin_uri if is_margin else self.base_uri
        )

    async def load_listen_key(self):
        self.logger.info("Obtain user stream listen key....")
        content, _ = await self.public.request_url(
            "/userDataStream", RestMethod.POST, headers=self.headers
        )
        # content, _ = await self.private_request_url('/userDataStream', RestMethod.POST)
        self.listen_key = content["listenKey"]

    # async def keep_alive_listen_key(self):
    #     self.logger.info("Keep alive listen key....")
    #     content, _ = await self.public.request_url("/userDataStream", RestMethod.POST, headers=self.headers)

    async def before_connect_private_streams(self):
        await self.load_listen_key()

    async def ws_private_connect(self) -> WebSocketClientProtocol:
        self.logger.info(
            f"Connecting to {self.websocket_name} websocket: {self.wss_url}"
        )
        conn = await websockets.connect(
            f"{self.wss_url}{self.listen_key}",
            ping_interval=300.0,
            loop=CoreBase.get_loop(),
            max_queue=5000,
        )
        return conn

    async def load_orders(self, symbol: Symbol, is_isolated: Optional[bool] = None):
        margin_str = "" if is_isolated is None else f"margin isolated={is_isolated}"
        self.logger.info(f"Load {symbol} {margin_str} orders")
        params = {
            "symbol": f"{symbol_to_binance(symbol).upper()}",
            "limit": MAX_ALL_ORDERS,
        }

        if is_isolated is not None:
            params["isIsolated"] = str(is_isolated).upper()

        content, _ = await self.private_request_url(
            f"/allOrders",
            RestMethod.GET,
            params=params,
            is_margin=is_isolated is not None
        )
        # also : time, 'isBestMatch', quoteQty
        self.orders[symbol] = {int(o["orderId"]): Order().from_rest(o) for o in content}
        pass

    async def load_all_orders(self, symbols: List[Symbol], is_isolated: Optional[bool] = None):
        tasks = [asyncio.create_task(self.load_orders(s, is_isolated=is_isolated)) for s in symbols]
        await asyncio.gather(*tasks)

    async def cancel_order(self, order: Order) -> Order:
        order = await self.cancel_order_by_id(symbol=order.symbol, order_id=order.id, is_isolated=order.is_isolated)
        return order

    async def cancel_order_by_id(self, symbol: Symbol,
                                 order_id: Optional[str] = None, client_order_id: Optional[str] = None,
                                 is_isolated: Optional[bool] = None) -> Order:
        params = {
            "symbol": f"{symbol.upper()}",
        }  # "timestamp"

        if order_id is not None:
            params["orderId"] = order_id

        if client_order_id is not None:
            params["origClientOrderId"] = client_order_id

        content, _ = await self.private_request_url(
            f"/order",
            RestMethod.DELETE,
            params=params,
            is_margin=is_isolated is not None
        )

        order = Order().from_rest(content)
        self._update_orders(order)
        self.logger.info(f"{order} canceled.")
        return order

    async def query_cross_margin_balance(self):
        content, _ = await self.private_request_url(
            f"/account",
            RestMethod.GET,
            is_margin=True
        )
        # {'asset': 'JASMY', 'free': '0.3485', 'locked': '0', 'borrowed': '0', 'interest': '0', 'netAsset': '0.3485'}

        user_assets = {a['asset']: dict_values_as_lambda(dict_pick_exclude(a, ['asset']), lambda a: float(a))
                       for a in content['userAssets']}

        return user_assets

    async def get_cross_margin_asset_balance(self, asset_name: str) -> Dict[str, Any]:
        user_assets = await self.spot.query_cross_margin_balance()
        return user_assets[asset_name]

    async def place_order(self, symbol: Symbol, side: Side, order_type: OrderType, quantity: float,
                          price: Optional[float] = None, stop_price: Optional[float] = None,
                          client_order_id: Optional[str] = None,
                          time_in_force: Optional[TimeInForce] = TimeInForce.GTC.value,
                          is_isolated: Optional[bool] = None,
                          side_effect_type: Optional[SideEffectType] = None,
                          reduce_only: Optional[bool] = None,
                          close_position: Optional[bool] = None):
        self.logger.info(f"Place {order_type} {side} {symbol} order -"
                         f" q: {quantity} p: {price} sp: {stop_price}")
        params = {
            "symbol": f"{symbol.upper()}",
            "side": side.value,
            "type": order_type.value,
            "quantity": f'{quantity:.{self.public.symbol_info[symbol].amount_precision}f}',
            "newOrderRespType": "FULL"
        }  # "timestamp"

        # quantity_field = "quoteOrderQty" if self.exchange_type == ExchangeType.SPOT else "quantity"
        # params[quantity_field] = quantity

        # !!!! futures - closePosition / reduceOnly

        if order_type != OrderType.MARKET:
            params["timeInForce"] = time_in_force

        if price is not None:
            params["price"] = f'{price:.{self.public.symbol_info[symbol].price_precision}f}'

        if stop_price is not None:
            params["stopPrice"] = f'{stop_price:.{self.public.symbol_info[symbol].price_precision}f}'

        if client_order_id is not None:
            params["newClientOrderId"] = client_order_id

        # -- MARGIN
        if is_isolated is not None:
            params["isIsolated"] = str(is_isolated).upper()

            if side_effect_type is not None:
                params["sideEffectType"] = side_effect_type.value


        #  -- FUTURES
        if self.exchange_type == ExchangeType.FUTURES:
            params["newOrderRespType"] = "RESULT"

            if reduce_only is not None:
                params["reduceOnly"] = str(reduce_only)

            if close_position is not None:
                params["closePosition"] = str(close_position)

        content, _ = await self.private_request_url(
            f"/order",
            RestMethod.POST,
            params=params,
            is_margin=is_isolated is not None
        )

        order = Order().from_rest(content)
        self._update_orders(order)
        self.logger.info(f"{order} placed.")
        return order

    async def ws_on_private_message(self, msg: Dict):
        # self.logger.info(msg)
        pass
        if "e" not in msg:
            self.logger.warning(msg)
            return

        channel = msg["e"]
        self.streams[channel] = datetime.utcnow()

        if channel == "executionReport":
            symbol = binance_to_symbol(msg["s"])

            if symbol not in self.orders.keys():
                self.orders[symbol] = {}

            ws_order = Order().from_ws(msg)
            self.orders[symbol][ws_order.id] = ws_order

            await asyncio.gather(
                *[
                    asyncio.create_task(c.callback(symbol, ws_order))
                    for c in self.callbacks
                    if c.feed == f"executionReport" and c.symbol == symbol
                ]
            )

        # if msg['e'] == 'outboundAccountPosition':
        #     self._update_balances(msg)
        #     return


if __name__ == "__main__":
    # api_key = "GXEyukpLh4aFnzFQZk1vD6NpCH1Tgxujo8uVYzK7oYjgXESZJ4W9lPHiKwZbshhy"
    # api_secret = "K4TUl94wvVScqGWOx6YMjDoZa8Fy7gbAB9BTovWDWnM8unxA52XLrZFhdhvldcnm"
    binance = PrivateBinance(api_key= Config.BINANCE_API_KEY, api_secret= global_config.BINANCE_API_SECRET)


    async def main():
        try:
            await binance.async_init()
            symbol_btc = SymbolStr("BTCUSDT")
            symbol_jasmy = SymbolStr("JASMYUSDT")
            await binance.load_all_orders([symbol_jasmy], is_isolated=False)
            result = await binance.query_cross_margin_balance()
            print(result)
            for o in copy(binance.orders[symbol_jasmy]).values():
                if o.active:
                    await binance.cancel_order(o)

            price = 0.0039
            quantity = 25
            spot_quantity = binance.public.get_asset_quantity(symbol_jasmy, price, quantity)
            # https://api.binance.com/sapi/v1/margin/order?symbol=JASMYUSDT&side=SELL&type=MARKET&quantity=6151.5&isIsolated=FALSE&sideEffectType=AUTO_REPAY
            await binance.place_order(symbol_jasmy, Side.SELL,
                                      order_type=OrderType.LIMIT, quantity=6145, price=price,
                                      is_isolated=False, side_effect_type=SideEffectType.AUTO_REPAY)

        except Exception as e:
            logging.error(add_traceback(e))


    asyncio.run(main())
