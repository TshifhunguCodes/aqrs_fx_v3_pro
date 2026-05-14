"""
Debug script to check available MT5 data range.
"""
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone

mt5.initialize()

symbol = "EURUSD"
print(f"Checking data for {symbol}...")

# Check M5
for bars in [500, 5000, 100000]:
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, bars)
    if rates is not None and len(rates) > 0:
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        print(f"  M5 {bars:>6} bars: {df['time'].iloc[0]} to {df['time'].iloc[-1]} ({len(df)} bars)")
    else:
        print(f"  M5 {bars:>6} bars: No data")

# Check H1
for bars in [500, 5000, 100000]:
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, bars)
    if rates is not None and len(rates) > 0:
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        print(f"  H1 {bars:>6} bars: {df['time'].iloc[0]} to {df['time'].iloc[-1]} ({len(df)} bars)")
    else:
        print(f"  H1 {bars:>6} bars: No data")

# Try copy_rates_range
from_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
to_date = datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc)
rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M5, from_date, to_date)
if rates is not None and len(rates) > 0:
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    print(f"\n  Range M5 2024-2026: {df['time'].iloc[0]} to {df['time'].iloc[-1]} ({len(df)} bars)")
else:
    print(f"\n  Range M5 2024-2026: No data returned")

mt5.shutdown()