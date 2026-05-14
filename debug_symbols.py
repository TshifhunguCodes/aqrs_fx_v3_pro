import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone

mt5.initialize()
for sym in ['GBPUSD', 'USDJPY', 'USDCHF']:
    rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 50000)
    if rates is not None and len(rates) > 0:
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        print(f'{sym} M5: {len(df)} bars, {df["time"].iloc[0]} to {df["time"].iloc[-1]}')
    else:
        print(f'{sym} M5: No data')
        
    rates_h1 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 50000)
    if rates_h1 is not None and len(rates_h1) > 0:
        df_h1 = pd.DataFrame(rates_h1)
        df_h1['time'] = pd.to_datetime(df_h1['time'], unit='s')
        print(f'{sym} H1: {len(df_h1)} bars, {df_h1["time"].iloc[0]} to {df_h1["time"].iloc[-1]}')
    else:
        print(f'{sym} H1: No data')
        
mt5.shutdown()