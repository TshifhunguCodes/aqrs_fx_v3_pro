"""
AQRS FX Pro V3 — Historical Backtest Engine
Walks through historical M5 + H1 data bar-by-bar, applies full strategy pipeline,
logs simulated trades, and prints a performance summary.
Uses copy_rates_from_pos for reliable data retrieval across any broker.
"""

import sys
import os
import copy
import csv
from datetime import datetime, timedelta, timezone
from collections import defaultdict

import MetaTrader5 as mt5
import pandas as pd
import numpy as np

# ── Ensure project root is on path ──────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from market.candles import add_indicators, merge_htf_context

from strategy.htf_bias import get_bias
from strategy.structure import classify_structure, premium_discount, detect_inducement
from strategy.liquidity import liquidity_sweep
from strategy.fvg import detect_fvg, detect_fvg_zones, price_in_fvg
from strategy.order_blocks import detect_order_block, detect_ob_zones, price_in_ob
from strategy.manipulation import manipulation_score
from strategy.candle_confirm import get_candle_confirmation
from strategy.session import current_session, is_valid_session
from strategy.scoring import calculate_score

from regime.volume_profile import build_volume_profile, vp_zone, vp_near_poc
from regime.market_lifecycle import classify_lifecycle
from regime.market_regime import classify_regime

from intelligence.unsupervised_model import predict_regime, score_modifier_for_regime
from intelligence.rl_agent import rl_approve
from risk.dynamic_exit import dynamic_sltp

from core.config import (
    MAX_OPEN_TRADES, MAX_DAILY_DRAWDOWN, PAIR_RISK
)
from core.logger import logger


# ── Suppress logging during backtest ────────────────────────────────────────
import logging
logging.getLogger("AQRS").setLevel(logging.ERROR)
import warnings
warnings.filterwarnings("ignore")


# ── Simulated account ───────────────────────────────────────────────────────
class SimAccount:
    def __init__(self, balance=10000):
        self.balance = balance
        self.peak_balance = balance
        self.open_positions = {}
        self._next_ticket = 1

    def can_open(self):
        if len(self.open_positions) >= MAX_OPEN_TRADES:
            return False, "MAX_TRADES"
        loss = (self.peak_balance - self.balance) / self.peak_balance if self.peak_balance > 0 else 0
        if loss >= MAX_DAILY_DRAWDOWN:
            return False, "DRAWDOWN"
        return True, "OK"

    def get_balance(self):
        return self.balance

    def next_ticket(self):
        t = self._next_ticket
        self._next_ticket += 1
        return t

    def open_trade(self, symbol, direction, entry, sl, tp, volume, rr, score, logic,
                   regime, lifecycle, phase, session, pd_zone, vp_zone, ml_regime):
        ticket = self.next_ticket()
        self.open_positions[ticket] = {
            "ticket": ticket,
            "symbol": symbol,
            "direction": direction,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "volume": volume,
            "rr": rr,
            "score": score,
            "logic": logic,
            "regime": regime,
            "lifecycle": lifecycle,
            "phase": phase,
            "session": session,
            "pd_zone": pd_zone,
            "vp_zone": vp_zone,
            "ml_regime": ml_regime,
            "open_time": None,
            "close_time": None,
            "pnl": 0,
            "exit_reason": "",
        }
        return ticket

    def check_exits(self, bar_time, high, low, close):
        closed = []
        tickets_to_remove = []
        for ticket, pos in self.open_positions.items():
            direction = pos["direction"]
            sl = pos["sl"]
            tp = pos["tp"]
            entry = pos["entry"]

            exit_reason = None
            exit_price = None

            if direction == "BUY":
                if low <= sl:
                    exit_reason = "SL"
                    exit_price = sl
                elif high >= tp:
                    exit_reason = "TP"
                    exit_price = tp
            else:
                if high >= sl:
                    exit_reason = "SL"
                    exit_price = sl
                elif low <= tp:
                    exit_reason = "TP"
                    exit_price = tp

            if exit_reason:
                pnl = (exit_price - entry) * pos["volume"] * 100000 if direction == "BUY" else (entry - exit_price) * pos["volume"] * 100000
                pnl = round(pnl, 2)
                pos["close_time"] = bar_time
                pos["pnl"] = pnl
                pos["exit_reason"] = exit_reason
                pos["exit_price"] = exit_price
                closed.append(copy.deepcopy(pos))
                tickets_to_remove.append(ticket)
                self.balance += pnl
                if self.balance > self.peak_balance:
                    self.peak_balance = self.balance

        for t in tickets_to_remove:
            del self.open_positions[t]
        return closed


def bt_lot_size(symbol, sl_dist_price, balance):
    risk_frac = PAIR_RISK.get(symbol, 0.005)
    risk_amount = balance * risk_frac
    if sl_dist_price > 0:
        lots = risk_amount / (sl_dist_price * 100000)
        lots = max(0.01, min(lots, 10.0))
        return round(lots, 2)
    return round(risk_amount / 100, 2)


def fetch_data(symbol):
    """Fetch M5 and H1 data using copy_rates_from_pos (works on any broker)."""
    tf_map = {"M5": mt5.TIMEFRAME_M5, "H1": mt5.TIMEFRAME_H1}

    # Fetch max available bars in batches
    m5_bars = []
    h1_bars = []
    batch_size = 1000  # Reduced for demo

    rates = mt5.copy_rates_from_pos(symbol, tf_map["M5"], 0, batch_size)
    if rates is not None and len(rates) > 0:
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df = df.sort_values('time').reset_index(drop=True)
        m5_bars = df
        print(f"  M5: {len(df)} bars from {df['time'].iloc[0]} to {df['time'].iloc[-1]}")

    rates = mt5.copy_rates_from_pos(symbol, tf_map["H1"], 0, batch_size)
    if rates is not None and len(rates) > 0:
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df = df.sort_values('time').reset_index(drop=True)
        h1_bars = df
        print(f"  H1: {len(df)} bars from {df['time'].iloc[0]} to {df['time'].iloc[-1]}")

    return m5_bars, h1_bars


def print_summary(trades, initial_balance):
    print(f"\n{'='*70}")
    print(f"PERFORMANCE SUMMARY")
    print(f"{'='*70}")

    if not trades:
        print("No trades were taken.")
        return

    total_trades = len(trades)
    winning_trades = [t for t in trades if t["pnl"] > 0]
    losing_trades = [t for t in trades if t["pnl"] < 0]
    break_even = [t for t in trades if t["pnl"] == 0]

    wins = len(winning_trades)
    losses = len(losing_trades)

    total_pnl = sum(t["pnl"] for t in trades)
    gross_profit = sum(t["pnl"] for t in winning_trades)
    gross_loss = sum(t["pnl"] for t in losing_trades)

    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    avg_win = (gross_profit / wins) if wins > 0 else 0
    avg_loss = (gross_loss / losses) if losses > 0 else 0
    avg_pnl = total_pnl / total_trades
    profit_factor = abs(gross_profit / gross_loss) if gross_loss != 0 else float('inf')

    # Max drawdown
    cumulative = initial_balance
    peak = initial_balance
    max_dd_pct = 0
    for t in trades:
        cumulative += t["pnl"]
        if cumulative > peak:
            peak = cumulative
        dd = (peak - cumulative) / peak * 100
        if dd > max_dd_pct:
            max_dd_pct = dd

    # Sharpe-like ratio
    pnl_values = np.array([t["pnl"] for t in trades])
    sharpe = np.mean(pnl_values) / (np.std(pnl_values) + 1e-9) * np.sqrt(252) if len(pnl_values) > 1 else 0

    final_balance = initial_balance + total_pnl
    total_return_pct = (final_balance - initial_balance) / initial_balance * 100

    # Trade duration
    durations = []
    for t in trades:
        if t.get("open_time") and t.get("close_time"):
            try:
                dur = (t["close_time"] - t["open_time"]).total_seconds() / 3600
                durations.append(dur)
            except:
                pass
    avg_duration = np.mean(durations) if durations else 0

    # By direction
    buy_trades = [t for t in trades if t["direction"] == "BUY"]
    sell_trades = [t for t in trades if t["direction"] == "SELL"]
    buy_pnl = sum(t["pnl"] for t in buy_trades)
    sell_pnl = sum(t["pnl"] for t in sell_trades)

    # By exit reason
    tp_trades = [t for t in trades if t.get("exit_reason") == "TP"]
    sl_trades = [t for t in trades if t.get("exit_reason") == "SL"]
    end_trades = [t for t in trades if t.get("exit_reason") == "END_OF_DATA"]

    # By symbol
    symbol_stats = defaultdict(lambda: {"trades": 0, "wins": 0, "pnl": 0})
    for t in trades:
        s = t.get("symbol", "UNKNOWN")
        symbol_stats[s]["trades"] += 1
        symbol_stats[s]["pnl"] += t["pnl"]
        if t["pnl"] > 0:
            symbol_stats[s]["wins"] += 1

    print(f"\n  ┌─────────────────────────────────────────────────┬─────────────┐")
    print(f"  │ Metric                                          │ Value        │")
    print(f"  ├─────────────────────────────────────────────────┼─────────────┤")
    print(f"  │ Initial Balance                                 │ ${initial_balance:>10,.2f} │")
    print(f"  │ Final Balance                                   │ ${final_balance:>10,.2f} │")
    print(f"  │ Total Return                                    │ {total_return_pct:>+10.2f}% │")
    print(f"  │ Total Net Profit                                │ ${total_pnl:>+10,.2f} │")
    print(f"  ├─────────────────────────────────────────────────┼─────────────┤")
    print(f"  │ Total Trades                                    │ {total_trades:>12} │")
    print(f"  │ Winning Trades                                  │ {wins:>12} │")
    print(f"  │ Losing Trades                                   │ {losses:>12} │")
    print(f"  │ Breakeven Trades                                │ {len(break_even):>12} │")
    print(f"  │ Win Rate                                        │ {win_rate:>11.2f}% │")
    print(f"  ├─────────────────────────────────────────────────┼─────────────┤")
    print(f"  │ Gross Profit                                    │ ${gross_profit:>+10,.2f} │")
    print(f"  │ Gross Loss                                      │ ${gross_loss:>+10,.2f} │")
    print(f"  │ Profit Factor                                   │ {profit_factor:>12.2f} │")
    print(f"  │ Average Trade                                   │ ${avg_pnl:>+10,.2f} │")
    print(f"  │ Average Winner                                  │ ${avg_win:>+10,.2f} │")
    print(f"  │ Average Loser                                   │ ${avg_loss:>+10,.2f} │")
    print(f"  ├─────────────────────────────────────────────────┼─────────────┤")
    print(f"  │ Max Drawdown                                    │ {max_dd_pct:>11.2f}% │")
    print(f"  │ Sharpe-like Ratio (annualized)                  │ {sharpe:>12.2f} │")
    print(f"  │ Average Trade Duration (hours)                  │ {avg_duration:>12.1f} │")
    print(f"  ├─────────────────────────────────────────────────┼─────────────┤")
    print(f"  │ BUY Trades                                      │ {len(buy_trades):>12} │")
    print(f"  │ BUY P&L                                         │ ${buy_pnl:>+10,.2f} │")
    print(f"  │ SELL Trades                                     │ {len(sell_trades):>12} │")
    print(f"  │ SELL P&L                                        │ ${sell_pnl:>+10,.2f} │")
    print(f"  ├─────────────────────────────────────────────────┼─────────────┤")
    print(f"  │ Hit TP                                          │ {len(tp_trades):>12} │")
    print(f"  │ Hit SL                                          │ {len(sl_trades):>12} │")
    print(f"  │ End of Data (flat)                              │ {len(end_trades):>12} │")
    print(f"  └─────────────────────────────────────────────────┴─────────────┘")

    # Per-symbol breakdown
    print(f"\n  ── Per-Symbol Breakdown ──")
    print(f"  {'Symbol':<12} {'Trades':<8} {'Wins':<6} {'Losses':<8} {'Win Rate':<10} {'P&L':<12}")
    print(f"  {'-'*56}")
    for s in sorted(symbol_stats.keys()):
        st = symbol_stats[s]
        wr = (st["wins"] / st["trades"] * 100) if st["trades"] > 0 else 0
        losses = st["trades"] - st["wins"]
        print(f"  {s:<12} {st['trades']:<8} {st['wins']:<6} {losses:<8} {wr:>7.2f}%  ${st['pnl']:>+8,.2f}")

    # Monthly breakdown
    print(f"\n  ── Monthly P&L Breakdown ──")
    monthly = defaultdict(float)
    monthly_trades = defaultdict(int)
    for t in trades:
        if t.get("close_time"):
            try:
                key = t["close_time"].strftime("%Y-%m")
                monthly[key] += t["pnl"]
                monthly_trades[key] += 1
            except:
                pass
    print(f"  {'Month':<10} {'Trades':<8} {'P&L':<14}")
    print(f"  {'-'*32}")
    for m in sorted(monthly.keys()):
        print(f"  {m:<10} {monthly_trades[m]:<8} ${monthly[m]:>+8,.2f}")


# ── Main backtest function ─────────────────────────────────────────────────
def run_backtest(symbols=None, balance=10000):
    if symbols is None:
        symbols = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF"]

    print(f"\n{'='*70}")
    print(f"AQRS FX Pro V3 — Historical Backtest")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Starting Balance: ${balance:,.0f}")
    print(f"{'='*70}\n")

    if not mt5.initialize():
        print("ERROR: MT5 initialization failed")
        return

    all_trades = []

    for symbol in symbols:
        print(f"\n{'─'*50}")
        print(f"Backtesting {symbol}...")
        print(f"{'─'*50}")

        account = SimAccount(balance=balance)

        # ── Fetch data ──────────────────────────────────────────────────────
        df_m5, df_h1 = fetch_data(symbol)
        if len(df_m5) < 300 or len(df_h1) < 50:
            print(f"  SKIP: insufficient data")
            continue

        # ── Add indicators ──────────────────────────────────────────────────
        df_m5 = add_indicators(df_m5)
        df_h1 = add_indicators(df_h1)

        # ── Walk through bars ───────────────────────────────────────────────
        min_bars = 300
        trades_for_symbol = 0

        for i in range(min_bars, len(df_m5)):
            df_slice = df_m5.iloc[:i+1].copy()
            current_bar = df_slice.iloc[-1]
            current_time = current_bar['time']
            current_price = current_bar['close']

            # Skip weekends
            if current_time.weekday() >= 5:
                continue

            # Check open positions
            closed = account.check_exits(
                current_time, current_bar['high'],
                current_bar['low'], current_bar['close']
            )
            for t in closed:
                all_trades.append(t)

            # ── Gates ───────────────────────────────────────────────────────
            ok, reason = account.can_open()
            if not ok:
                continue

            if not is_valid_session(strict=False):
                continue

            # ── Build context ───────────────────────────────────────────────
            h1_slice = df_h1[df_h1['time'] <= current_time].copy()
            if len(h1_slice) < 50:
                continue

            try:
                df_context = merge_htf_context(df_slice, h1_slice)
            except Exception:
                df_context = df_slice

            if df_context.isnull().values.any():
                df_context = df_context.bfill().ffill()

            last_row = df_context.iloc[-1]
            atr = last_row.get('atr', 0)

            # ── HTF bias ────────────────────────────────────────────────────
            bias = get_bias(h1_slice)
            if bias == "RANGE":
                continue

            direction = "BUY" if bias == "BULLISH" else "SELL"

            # ── Candle confirmation ─────────────────────────────────────────
            candle_confirm = get_candle_confirmation(df_context, direction)
            if not candle_confirm["confirmed"]:
                continue

            # ── Structure ───────────────────────────────────────────────────
            structure = classify_structure(df_context)
            pd_zone = premium_discount(structure["last_sh"], structure["last_sl"], current_price)

            # ── Regime + Lifecycle ──────────────────────────────────────────
            regime = classify_regime(df_context, h1_slice)
            lifecycle = classify_lifecycle(df_context, direction)

            if not lifecycle["allow_new_entry"]:
                continue

            # ── Volume Profile ──────────────────────────────────────────────
            vp = build_volume_profile(df_context.tail(100))
            vp_z = vp_zone(current_price, vp)
            near_poc = vp_near_poc(current_price, vp, atr)

            # ── SMC zones ───────────────────────────────────────────────────
            fvg_signal = detect_fvg(df_context)
            fvg_zones = detect_fvg_zones(df_context, lookback=50)
            in_fvg = price_in_fvg(current_price, fvg_zones,
                                  "BULLISH" if direction == "BUY" else "BEARISH")

            ob_signal = detect_order_block(df_context)
            ob_zones = detect_ob_zones(df_context, lookback=60)
            in_ob = price_in_ob(current_price, ob_zones,
                                "BULLISH" if direction == "BUY" else "BEARISH")

            # ── MTF alignment ───────────────────────────────────────────────
            h1_last = h1_slice.iloc[-1] if len(h1_slice) > 0 else last_row
            mtf_aligned = (
                (last_row.get('ema8', 0) > last_row.get('ema21', 0) and
                 h1_last.get('ema8', 0) > h1_last.get('ema21', 0))
                if direction == "BUY" else
                (last_row.get('ema8', 0) < last_row.get('ema21', 0) and
                 h1_last.get('ema8', 0) < h1_last.get('ema21', 0))
            )

            macd_hist = last_row.get('macd_hist', 0)
            macd_aligned = (macd_hist > 0 if direction == "BUY" else macd_hist < 0)

            # ── Score ───────────────────────────────────────────────────────
            score_data = {
                "bias": bias,
                "structure_trend": structure["trend"],
                "bos": structure["bos"],
                "choch": structure["choch"],
                "liquidity": liquidity_sweep(df_context),
                "fvg": fvg_signal,
                "ob": ob_signal,
                "price_in_fvg": in_fvg,
                "price_in_ob": in_ob,
                "manipulation": manipulation_score(df_context, symbol),
                "candle_confirm": candle_confirm,
                "premium_discount": pd_zone,
                "inducement": detect_inducement(df_context, direction),
                "valid_session": is_valid_session(strict=True),
                "direction": direction,
                "lifecycle_modifier": lifecycle["score_modifier"],
                "regime_modifier": regime["score_modifier"],
                "ml_regime": predict_regime(df_context),
                "vp_zone": vp_z,
                "near_poc": near_poc,
                "mtf_aligned": mtf_aligned,
                "adx": last_row.get('adx', 0),
                "macd_aligned": macd_aligned,
            }

            score = calculate_score(score_data)
            if score < 75:
                continue

            # ── ML gate ─────────────────────────────────────────────────────
            ml_regime = predict_regime(df_context)
            regime_delta = score_modifier_for_regime(ml_regime, direction)
            rl_result = rl_approve(ml_regime, pd_zone, lifecycle["phase"],
                                   candle_confirm["score"], direction)
            if not (rl_result["approved"] and regime_delta > -15):
                continue

            # ── Dynamic exits ───────────────────────────────────────────────
            exits = dynamic_sltp(
                entry=current_price, atr=atr, direction=direction,
                regime=regime["regime"], phase=lifecycle["phase"],
                bb_pct=last_row.get('bb_pct', 0.5),
            )

            # ── Position sizing ─────────────────────────────────────────────
            bal = account.get_balance()
            volume = bt_lot_size(symbol, exits["sl_dist"], bal)

            # ── Open trade ──────────────────────────────────────────────────
            ticket = account.open_trade(
                symbol=symbol, direction=direction,
                entry=current_price, sl=exits["sl"], tp=exits["tp"],
                volume=volume, rr=exits["rr"], score=score,
                logic=exits["logic"],
                regime=regime["regime"], lifecycle=lifecycle["phase"],
                phase=current_session(),
                session=current_session(),
                pd_zone=pd_zone, vp_zone=vp_z,
                ml_regime=ml_regime,
            )
            account.open_positions[ticket]["open_time"] = current_time
            trades_for_symbol += 1

        # ── Force-close remaining positions at end ──────────────────────────
        last_time = df_m5['time'].iloc[-1]
        for ticket in list(account.open_positions.keys()):
            pos = account.open_positions[ticket]
            pos["close_time"] = last_time
            pos["exit_price"] = pos["entry"]
            pos["exit_reason"] = "END_OF_DATA"
            pos["pnl"] = 0
            all_trades.append(pos)
            del account.open_positions[ticket]

        print(f"  Trades: {trades_for_symbol} | "
              f"Final: ${account.balance:>,.2f} | "
              f"Return: {(account.balance-balance)/balance*100:+.2f}%")

    mt5.shutdown()

    # ── Print summary ──────────────────────────────────────────────────────
    print_summary(all_trades, balance)

    # ── Save to CSV ────────────────────────────────────────────────────────
    if all_trades:
        csv_path = f"backtest_results.csv"
        with open(csv_path, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(all_trades[0].keys()),
                               extrasaction='ignore')
            w.writeheader()
            w.writerows(all_trades)
        print(f"\nTrade log saved to: {csv_path}")

    return all_trades


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AQRS FX Pro V3 Backtest")
    parser.add_argument("--symbols", nargs="+",
                        default=["EURUSD", "GBPUSD", "USDJPY", "USDCHF"],
                        help="Symbols to backtest")
    parser.add_argument("--balance", type=float, default=10000,
                        help="Starting balance")
    args = parser.parse_args()
    run_backtest(symbols=args.symbols, balance=args.balance)