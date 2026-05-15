import MetaTrader5 as mt5


def get_spread(symbol):
    tick = mt5.symbol_info_tick(symbol)
    info = mt5.symbol_info(symbol)
    if not tick or not info or not info.point:
        return float("inf")

    return abs(tick.ask - tick.bid) / info.point
