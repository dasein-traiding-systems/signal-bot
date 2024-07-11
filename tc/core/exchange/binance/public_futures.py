from core.exchange.binance.common import get_filter_value
from core.exchange.binance.public import PublicBinance, get_symbol_info
from core.exchange.common.mappers import binance_to_symbol, symbol_to_binance
from core.types import RestMethod, Singleton

BASE_FUTURES_URI = "https://fapi.binance.com/fapi/v1"
WSS_URL = "wss://fstream.binance.com/ws/"


class PublicFuturesBinance(PublicBinance, metaclass=Singleton):
    base_uri = BASE_FUTURES_URI
    wss_url = WSS_URL  # TODO: refactor ANOTHER approach each URL onw stream

    async def load_mark_prices(self):
        content, _ = await self.request_url(f"/premiumIndex", RestMethod.GET)
        self.mark_prices_ = self.mark_prices = {
            binance_to_symbol(i["symbol"]): float(i["markPrice"]) for i in content
        }

    async def load_exchange_info(self):
        content, _ = await self.request_url("/exchangeInfo")

        rateLimits = content["rateLimits"]
        weight_limit_1m = int(
            get_filter_value(
                rateLimits, "REQUEST_WEIGHT", "limit", name_of_filter="rateLimitType"
            )
        )
        raw_requests_5m = int(
            get_filter_value(
                rateLimits,
                "RAW_REQUESTS",
                "limit",
                name_of_filter="rateLimitType",
                default=weight_limit_1m,
            )
        )

        self.request_limiter.init(weight_limit_1m, raw_requests_5m)

        for s in content["symbols"]:
            if s["status"] == "TRADING":
                self.symbol_info[(s["symbol"])] = get_symbol_info(
                    s, is_futures=True
                )
