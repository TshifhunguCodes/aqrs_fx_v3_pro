import MetaTrader5 as mt5
import pandas as pd


class MT5Connector:

    def connect(self):

        if not mt5.initialize():
            raise Exception("MT5 connection failed")

        print("MT5 Connected")

    def get_rates(self, symbol, timeframe, bars=500):

        tf_map = {
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4
        }

        rates = mt5.copy_rates_from_pos(
            symbol,
            tf_map[timeframe],
            0,
            bars
        )

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        return df