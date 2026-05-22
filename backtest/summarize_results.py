import pandas as pd
import numpy as np
from collections import defaultdict

PATH = "../backtest_results.csv"
import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PATH = os.path.join(ROOT, 'backtest_results.csv')

def max_drawdown(pnls):
    cum = 0
    peak = 0
    max_dd = 0
    for p in pnls:
        cum += p
        peak = max(peak, cum)
        dd = peak - cum
        if peak > 0:
            max_dd = max(max_dd, dd / peak * 100)
    return max_dd


def summarize(path=PATH):
    try:
        df = pd.read_csv(path, parse_dates=["open_time","close_time"], dayfirst=False, encoding='utf-8')
    except Exception:
        df = pd.read_csv(path, parse_dates=["open_time","close_time"], dayfirst=False, encoding='latin-1')
    symbols = sorted(df['symbol'].unique())

    for s in symbols:
        sdf = df[df['symbol'] == s].copy()
        trades = len(sdf)
        wins = (sdf['pnl'] > 0).sum()
        losses = (sdf['pnl'] < 0).sum()
        breakeven = (sdf['pnl'] == 0).sum()
        total_pnl = sdf['pnl'].sum()
        gross_profit = sdf.loc[sdf['pnl']>0,'pnl'].sum()
        gross_loss = sdf.loc[sdf['pnl']<0,'pnl'].sum()
        win_rate = wins / trades * 100 if trades>0 else 0
        avg_win = sdf.loc[sdf['pnl']>0,'pnl'].mean() if wins>0 else 0
        avg_loss = sdf.loc[sdf['pnl']<0,'pnl'].mean() if losses>0 else 0
        profit_factor = abs(gross_profit / gross_loss) if gross_loss!=0 else float('inf')

        # durations
        durations = []
        for _,row in sdf.iterrows():
            try:
                if pd.notnull(row['open_time']) and pd.notnull(row['close_time']):
                    dur = (row['close_time'] - row['open_time']).total_seconds() / 3600
                    durations.append(dur)
            except Exception:
                pass
        avg_duration = np.mean(durations) if durations else 0

        # max drawdown on symbol equity curve
        pnls = list(sdf['pnl'].values)
        mdd = max_drawdown(pnls)

        buy_pnl = sdf.loc[sdf['direction']=='BUY','pnl'].sum()
        sell_pnl = sdf.loc[sdf['direction']=='SELL','pnl'].sum()
        buy_trades = len(sdf[sdf['direction']=='BUY'])
        sell_trades = len(sdf[sdf['direction']=='SELL'])

        print(f"\n{'='*60}\nSymbol: {s}\n{'='*60}")
        print(f"Trades: {trades}  Wins: {wins}  Losses: {losses}  Breakeven: {breakeven}")
        print(f"Total P&L: ${total_pnl:+.2f}  Gross P: ${gross_profit:+.2f}  Gross L: ${gross_loss:+.2f}")
        print(f"Win Rate: {win_rate:.2f}%  Avg Win: ${avg_win:.2f}  Avg Loss: ${avg_loss:.2f}  Profit Factor: {profit_factor:.2f}")
        print(f"Buy Trades: {buy_trades}  Buy P&L: ${buy_pnl:+.2f}  Sell Trades: {sell_trades}  Sell P&L: ${sell_pnl:+.2f}")
        print(f"Average Duration (hrs): {avg_duration:.2f}  Max Drawdown (%): {mdd:.2f}")

if __name__ == '__main__':
    summarize()
