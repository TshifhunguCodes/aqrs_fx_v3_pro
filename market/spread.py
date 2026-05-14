import MetaTrader5 as mt5


def get_spread(symbol):

    tick = mt5.symbol_info_tick(symbol)

    spread = abs(tick.ask - tick.bid)

    return spread * 10000