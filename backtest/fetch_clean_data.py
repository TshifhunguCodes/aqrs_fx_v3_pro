"""Fetch raw M5/H1 data from MT5 for configured symbols and save raw + cleaned CSVs.

Usage: python backtest/fetch_clean_data.py [--symbols EURUSD GBPUSD ...] [--bars_m5 50000] [--bars_h1 5000]
"""
import os
import sys
import argparse
import pandas as pd
import MetaTrader5 as mt5

# Ensure project root is on path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

from core.config import SYMBOLS
from market.mt5_connector import MT5Connector
from market.candles import add_indicators

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RAW_DIR = os.path.join(ROOT, 'data', 'raw')
CLEAN_DIR = os.path.join(ROOT, 'data', 'clean')

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(CLEAN_DIR, exist_ok=True)


def save_df(df, path):
    try:
        df.to_csv(path, index=False)
        print(f"  Saved: {path} ({len(df)} rows)")
    except Exception as e:
        print(f"  Failed saving {path}: {e}")


def fetch_symbol(symbol, bars_m5=50000, bars_h1=5000):
    conn = MT5Connector()
    resolved = conn.resolve_symbol(symbol)
    print(f"Symbol {symbol} -> broker name: {resolved}")

    tf_map = {'M5': mt5.TIMEFRAME_M5, 'H1': mt5.TIMEFRAME_H1}

    for tf, bars in (('M5', bars_m5), ('H1', bars_h1)):
        try:
            rates = mt5.copy_rates_from_pos(resolved, tf_map[tf], 0, bars)
        except Exception as e:
            print(f"  Error fetching {resolved} {tf}: {e}")
            rates = None

        if rates is None or len(rates) == 0:
            print(f"  No data for {resolved} {tf}")
            continue

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df = df.sort_values('time').reset_index(drop=True)

        raw_path = os.path.join(RAW_DIR, f"{symbol}_{tf}_raw.csv")
        save_df(df, raw_path)

        # Cleaned: add indicators (if available) and save
        try:
            cdf = add_indicators(df.copy())
            clean_path = os.path.join(CLEAN_DIR, f"{symbol}_{tf}_clean.csv")
            save_df(cdf, clean_path)
        except Exception as e:
            print(f"  Failed to add indicators for {symbol} {tf}: {e}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbols', nargs='+', default=SYMBOLS, help='Symbols to fetch')
    parser.add_argument('--bars_m5', type=int, default=50000)
    parser.add_argument('--bars_h1', type=int, default=5000)
    args = parser.parse_args()

    if not mt5.initialize():
        print("ERROR: MT5 initialization failed")
        raise SystemExit(1)

    print(f"Fetching data for: {', '.join(args.symbols)}")
    for s in args.symbols:
        print('\n' + '-'*60)
        print(f"Fetching {s}...")
        fetch_symbol(s, bars_m5=args.bars_m5, bars_h1=args.bars_h1)

    mt5.shutdown()
    print('\nDone.')
