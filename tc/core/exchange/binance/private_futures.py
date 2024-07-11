import asyncio
import time
from datetime import datetime
from typing import Dict

from core.base import CoreBase
from core.exchange.binance.entities import Order, Position
from core.exchange.binance.private import PrivateBinance
from core.exchange.binance.public_futures import BASE_FUTURES_URI, WSS_URL, PublicFuturesBinance
from core.exchange.common.mappers import binance_to_symbol, symbol_to_binance
from core.types import RestMethod, Symbol, SymbolStr, Side, OrderType, ExchangeType
from core.utils.logs import setup_logger, add_traceback
import logging

MAX_ALL_ORDERS = 100


class PrivateFuturesBinance(PrivateBinance):
    exchange = "binance"
    base_uri = BASE_FUTURES_URI
    wss_url = WSS_URL
    exchange_type = ExchangeType.FUTURES

    def __init__(self, api_key: str, api_secret: str):
        super().__init__(api_key, api_secret)
        self.websocket_name = "binance_futures_private"
        self.positions: Dict[Symbol, Position] = {}
        self.logger = setup_logger("private_binance_futures")
        self.public = PublicFuturesBinance()

    async def load_listen_key(self):
        self.logger.info("Obtain user stream listen key....")
        content, _ = await self.public.request_url(
            "/listenKey", RestMethod.POST, headers=self.headers
        )
        self.listen_key = content["listenKey"]

    async def load_user_trades(self, symbol: Symbol):
        self.logger.info(f"Load {symbol} user_trades")
        timestamp = int(time.time() * 1000)
        content, _ = await self.private_request_url(
            f"/allOrders",
            RestMethod.GET,
            params={
                "symbol": f"{symbol_to_binance(symbol).upper()}",
                "limit": MAX_ALL_ORDERS,
                "timestamp": timestamp,
            },
        )
        # also : time, 'isBestMatch', quoteQty
        pass

    def _get_position(self, symbol: Symbol):
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol)

        return self.positions[symbol]

    def _remove_position(self, symbol: Symbol):
        if symbol in self.positions:
            del self.positions[symbol]

    async def ws_on_private_message(self, msg: Dict):
        self.logger.info(msg)
        pass
        if "e" not in msg:
            self.logger.warning(msg)
            return

        channel = msg["e"]
        self.streams[channel] = datetime.utcnow()

        if channel == "ACCOUNT_UPDATE":
            positions_ws = msg.get("a", {}).get("P", [])
            trade_update_time = msg["T"]
            callbacks = []
            for p in positions_ws:
                symbol = binance_to_symbol(p["s"])
                position = self._get_position(symbol).update_from_ws(
                    p, trade_update_time
                )
                callbacks += [
                    asyncio.create_task(c.callback(position))
                    for c in self.callbacks
                    if c.feed == f"position"
                ]

            await asyncio.gather(*callbacks)

        elif channel == "ORDER_TRADE_UPDATE":
            trade_update_time = msg["T"]
            order_ws = msg["o"]
            symbol = binance_to_symbol(order_ws["s"])
            order = Order().from_ws(order_ws, trade_update_time)
            position = self._get_position(symbol).update_order(order)

            await asyncio.gather(
                *[
                    asyncio.create_task(c.callback(position, order))
                    for c in self.callbacks
                    if c.feed == f"position"
                ]
            )

            # if position was closed = clear
            if position.closed:
                del self.positions[position.symbol]
                self.logger.info(f"Position {position} closed.")


if __name__ == "__main__":
    api_key = "GXEyukpLh4aFnzFQZk1vD6NpCH1Tgxujo8uVYzK7oYjgXESZJ4W9lPHiKwZbshhy"
    api_secret = "K4TUl94wvVScqGWOx6YMjDoZa8Fy7gbAB9BTovWDWnM8unxA52XLrZFhdhvldcnm"

    binance = PrivateFuturesBinance(api_key=api_key, api_secret=api_secret)


    async def main():
        try:
            await binance.async_init()
            symbol_btc = SymbolStr("BTCUSDT")
            symbol_icx = SymbolStr("ICXUSDT")
            await binance.load_all_orders([symbol_icx])
            order = await binance.place_order(symbol_icx, Side.BUY,
                                              order_type=OrderType.MARKET, quantity=20, reduce_only=True)
            print(order)
            # for o in binance.orders[symbol_btc].values():
            #     if o.active:
            #         await binance.cancel_order(o)



        except Exception as e:
            logging.error(add_traceback(e))


    asyncio.run(main())
