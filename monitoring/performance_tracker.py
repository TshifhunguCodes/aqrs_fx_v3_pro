"""
Performance Tracker
Win rate, profit factor, Sharpe, drawdown, equity curve from CSV journal.
"""
import pandas as pd
import numpy as np
import os
from analytics.trade_journal import CLOSED_FILE
from core.logger import logger


def load_closed() -> pd.DataFrame:
    if not os.path.exists(CLOSED_FILE):
        return pd.DataFrame()
    return pd.read_csv(CLOSED_FILE, parse_dates=["timestamp"])


def compute_stats(df: pd.DataFrame = None) -> dict:
    if df is None:
        df = load_closed()
    if df.empty or "pnl" not in df.columns:
        return {}

    pnl = df["pnl"].astype(float)

    wins   = pnl[pnl > 0]
    losses = pnl[pnl < 0]

    win_rate      = len(wins) / len(pnl) if len(pnl) > 0 else 0
    avg_win       = wins.mean()  if len(wins)   > 0 else 0
    avg_loss      = losses.mean() if len(losses) > 0 else 0
    profit_factor = (wins.sum() / abs(losses.sum())) if losses.sum() != 0 else float('inf')

    equity = pnl.cumsum()
    rolling_max   = equity.cummax()
    drawdown      = equity - rolling_max
    max_drawdown  = drawdown.min()

    returns = pnl / pnl.abs().mean() if pnl.abs().mean() > 0 else pnl
    sharpe  = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0

    stats = {
        "total_trades":  len(pnl),
        "win_rate":      round(win_rate, 4),
        "avg_win":       round(avg_win, 2),
        "avg_loss":      round(avg_loss, 2),
        "profit_factor": round(profit_factor, 3),
        "max_drawdown":  round(max_drawdown, 2),
        "sharpe":        round(sharpe, 3),
        "net_pnl":       round(pnl.sum(), 2),
    }

    logger.info(f"Performance | {stats}")
    return stats


def print_summary():
    stats = compute_stats()
    if not stats:
        print("No closed trades yet.")
        return
    print("\n─── AQRS FX Pro V3 — Performance ───")
    for k, v in stats.items():
        print(f"  {k:<18}: {v}")
    print("────────────────────────────────────\n")
