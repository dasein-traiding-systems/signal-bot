from functools import lru_cache
from typing import Optional

from core.types import Asset, Symbol, SymbolStr


@lru_cache()
def symbol_to_binance(symbol: Symbol) -> SymbolStr:
    return symbol
    # return SymbolStr(f"{symbol[0]}{symbol[1]}".upper())


@lru_cache()
def binance_to_symbol(symbol: str, quote: Optional[Asset] = None) -> Symbol:
    return Symbol(symbol)
    # if quote is None:
    #     quote = detect_quote(symbol)
    #
    # return Asset(symbol.upper().replace(quote, "")), quote


def detect_quote(symbol: str) -> Asset:
    symbol_ = symbol.upper()
    if symbol_[-4:] in ["USDT", "BUSD"]:
        return Asset(symbol_[-4:])
    else:
        return Asset(symbol_[:-3])

