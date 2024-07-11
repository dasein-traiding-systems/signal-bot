import asyncio
from typing import Any
from time import sleep
from core.utils.dict_ import dict_any_value


# used_weight_1m = int(dictAnyValueOf(['x-mbx-used-weight-1m', 'x-sapi-used-weight-1m', 'x-mbx-used-weight'],
#                                     headers, BinanceRestApi.weight_limit_1m))
#
# slow_down_time = used_weight_1m / BinanceRestApi.weight_limit_1m
# second = pd.to_datetime(headers['date']).second
# delay = slow_down_time if 'retry-after' not in client.response.headers else int(headers['retry-after'])
# BinanceRestApi.rate_limit_info = f'Delay: {round(delay, 3)}s  ' \
#                                  f'Weight: {used_weight_1m}/{BinanceRestApi.weight_limit_1m} ' \
#                                  f'Seconds: {60 - second}'
# sleep(delay)

# 'x-mbx-used-weight': '1', 'x-mbx-used-weight-1m': '1', 'Content-Encoding': 'gzip', 'Strict-Transport-Security': 'max-age=31536000; includeSubdomains', 'X-Frame-Options': 'SAMEORIGIN', 'X-Xss-Protection': '1; mode=block', 'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy': "default-src 'self'", 'X-Content-Security-Policy': "default-src 'self'", 'X-WebKit-CSP': "default-src 'self'", 'Cache-Control': 'no-cache, no-store, must-revalidate', 'Pragma': 'no-cache', 'Expires': '0', 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS', 'X-Cache': 'Miss from cloudfront', 'Via': '1.1 a8f46a0f81ad5be499efe8a1372dd92a.cloudfront.net (CloudFront)', 'X-Amz-Cf-Pop': 'BOM78-P4', 'X-Amz-Cf-Id': '6L3i7UY6FWQDdgdATqZoLzT9vSs5VsfDcrgLYfEd-AD1sFqqBEHzpQ==')>


class BinanceRequestLimiter(object):
    weight_limit_1m = 10
    raw_requests_5m = 2000
    info = ""
    initialized = False

    def __init__(self):
        super().__init__()
        # BinanceRestApi.weight_limit_1m = int(
        #     [v['limit'] for v in exchange_info['rateLimits'] if v['rateLimitType'] == 'REQUEST_WEIGHT'][0])
        #

    def init(self, weight_limit_1m: int, raw_requests_5m: int):
        self.weight_limit_1m = weight_limit_1m
        self.raw_requests_5m = raw_requests_5m
        self.initialized = True

    async def delay(self, resp: Any):
        if not self.initialized or resp is None:
            return

        headers = resp.headers
        used_weight_1m = int(
            dict_any_value(
                ["x-mbx-used-weight-1m", "x-sapi-used-weight-1m", "x-mbx-used-weight"],
                headers,
                self.weight_limit_1m,
            )
        )

        slow_down_time = used_weight_1m / self.weight_limit_1m
        # second = pd.to_datetime(headers['date']).second
        # f'Seconds: {60 - second}'

        delay = (
            slow_down_time
            if "retry-after" not in headers
            else int(headers["retry-after"])
        )

        self.info = (
            f"Delay: {round(delay, 3)}s  "
            f"Weight: {used_weight_1m}/{self.weight_limit_1m} "
            f"Raw: /{self.raw_requests_5m} "
        )
        print(self.info)
        sleep(delay)
        # await asyncio.sleep(delay)
