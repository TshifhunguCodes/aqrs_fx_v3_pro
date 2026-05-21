import MetaTrader5 as mt5
from core.logger import logger


class EntryExecutor:

    def execute(
        self,
        symbol,
        direction,
        volume,
        sl,
        tp,
        comment="AQRS_FX_PRO",
        magic=777
    ):

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.error(f"{symbol} tick data unavailable - cannot execute")
            return None

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

        # Build base request — crucially, do NOT include type_filling
        # as many brokers reject explicit filling modes with retcode 10030.
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": magic,
            "comment": comment[:31],
            "type_time": mt5.ORDER_TIME_GTC,
        }

        result = mt5.order_send(request)

        # If order failed, try with type_filling=FOK(0) as fallback
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.warning(
                f"{symbol} order retcode={result.retcode if result else 'None'} "
                f"- trying with type_filling=FOK"
            )
            request["type_filling"] = mt5.ORDER_FILLING_FOK
            result = mt5.order_send(request)

        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(
                f"{symbol} ✅ order placed | ticket={result.order} | "
                f"vol={volume} | price={price:.5f} | sl={sl:.5f} | tp={tp:.5f}"
            )
        else:
            logger.error(
                f"{symbol} ❌ order failed | retcode={result.retcode if result else 'None'} | "
                f"comment={result.comment if result else mt5.last_error()}"
            )

        return result
