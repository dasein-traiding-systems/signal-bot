from typing import Any, Dict, Optional


class CoreBaseException(Exception):
    def __init__(self, *args, **kwargs):
        pass

# critical
# {'code': -2015, 'msg': 'Invalid API-key, IP, or permissions for action.'}

# minor
# {'code': -1102, 'msg': "Mandatory parameter ***"}
# {'code': -2010, 'msg': 'Account has insufficient balance for requested action.'}
# {'code': -2011, 'msg': 'Unknown order sent.'}
# Precision is over the maximum defined for this asset. (-1111)
#  Order's notional must be no smaller than 5.0 (unless you choose reduce only) (-4164)
# Not all sent parameters were read; read '8' parameter(s) but was sent '10'. (-1104)
#  Mandatory parameter 'sideEffectType' was not sent, was empty/null, or malformed. (-1102)
# {'code': -1013, 'msg': 'Filter failure: MIN_NOTIONAL'}

# Timestamp for this request is outside of the recvWindow. (-1021)



# Your borrow amount has exceed maximum borrow amount. (-3006)
#  Account has insufficient balance for requested action. (-2010)

# MARGIN PROBLEMS
# The system does not have enough asset now. (-3045)
#  Margin account are not allowed to trade this trading pair. (-3021)
# {'code': -11001, 'msg': 'Isolated margin account does not exist.'}
#  Not a valid margin asset. (-3027)

def apiExceptionFactory( content: Optional[Dict], response: Any)->Exception:
    if content is not None:
        code = content.get("code", None)
        if code == -2011:
            return UnknownOrderApiException(content=content, response=response)
        elif code == -2010:  # Account has insufficient balance for requested action
            return BalanceApiException(content=content, response=response)
        elif code == -3045:
            return ShouldRetryApiException(content=content, response=response)
        elif code == [-3021, -11001, -3027]:
            return NotAllowedApiException(content=content, response=response)
        elif code in [-1104, -1102, -1013, -1111]:
            return IncorrectParamsApiException(content=content, response=response)
        elif code in [-3006]:
            return MarginBalanceApiException(content=content, response=response)

    return ExchangeApiException(content=content, response=response)


class ExchangeApiException(CoreBaseException):
    def __init__(self,  *args, **kwargs):
        content: Optional[Dict] = kwargs["content"]
        self.response = kwargs["response"]
        self.url = self.response.url
        self.status = self.response.status
        self.code = content.get("code", None)
        self.message = content.get("msg", None)
        self.stop = self.code in [-2015]
        self.balance_problem = self.code in [-2010]

    def __str__(self):
        stop_ = " - !HALT! - " if self.stop else ""
        return f'{self.url} [{self.status}] \r\n {self.message} ({self.code}){stop_}'


class UnknownOrderApiException(ExchangeApiException):
    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)


class BalanceApiException(ExchangeApiException):
    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)


class ShouldRetryApiException(ExchangeApiException):
    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)


class IncorrectParamsApiException(ExchangeApiException):
    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)


class MarginBalanceApiException(ExchangeApiException):
    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)


class NotAllowedApiException(ShouldRetryApiException):
    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)