import MetaTrader5 as mt5
import pandas as pd
from core.config import SYMBOL_SUFFIXES


class MT5Connector:

    def connect(self):

        if not mt5.initialize():
            raise Exception("MT5 connection failed")

        print("MT5 Connected")

    def resolve_symbol(self, preferred_symbol):
        """Find the broker's tradable variant for a configured FX symbol."""
        candidates = [preferred_symbol]
        if "." in preferred_symbol:
            candidates.append(preferred_symbol.split(".")[0])
        candidates.extend(f"{preferred_symbol}{suffix}" for suffix in SYMBOL_SUFFIXES if suffix)

        for candidate in dict.fromkeys(candidates):
            info = mt5.symbol_info(candidate)
            if info:
                if not info.visible:
                    mt5.symbol_select(candidate, True)
                return candidate

        all_symbols = mt5.symbols_get() or []
        compact_preferred = preferred_symbol.replace(".", "").upper()
        for item in all_symbols:
            compact_name = item.name.replace(".", "").upper()
            if compact_name.startswith(compact_preferred):
                mt5.symbol_select(item.name, True)
                return item.name

        return preferred_symbol

    def get_rates(self, symbol, timeframe, bars=500):
        symbol = self.resolve_symbol(symbol)

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
        if df.empty:
            return df
        df['time'] = pd.to_datetime(df['time'], unit='s')

        return df
