import MetaTrader5 as mt5


class EntryExecutor:

    def execute(
        self,
        symbol,
        direction,
        volume,
        sl,
        tp
    ):

        tick = mt5.symbol_info_tick(symbol)

        price = (
            tick.ask
            if direction == "BUY"
            else tick.bid
        )

        order_type = (
            mt5.ORDER_TYPE_BUY
            if direction == "BUY"
            else mt5.ORDER_TYPE_SELL
        )

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 777,
            "comment": "AQRS_FX_PRO",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC
        }

        return mt5.order_send(request)