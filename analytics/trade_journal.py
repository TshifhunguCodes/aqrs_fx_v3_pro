"""
Trade Journal V3
Logs all trades to CSV, scans MT5 for closed trades, triggers RL updates.
"""
import csv, os
from datetime import datetime, timezone

try:
    import MetaTrader5 as mt5
    MT5_OK = True
except ImportError:
    MT5_OK = False

from core.logger import logger

JOURNAL_FILE = "trades_journal.csv"
CLOSED_FILE  = "closed_trades.csv"

JOURNAL_COLS = [
    "timestamp", "symbol", "direction", "score", "entry", "sl", "tp",
    "sl_dist", "rr", "structure", "pd_zone", "session", "regime",
    "lifecycle", "vp_zone", "ml_regime", "rl_approved", "exit_logic",
    "confirmations"
]


def log_trade(data: dict):
    exists = os.path.exists(JOURNAL_FILE)
    with open(JOURNAL_FILE, 'a', newline='') as f:
        w = csv.DictWriter(f, fieldnames=JOURNAL_COLS, extrasaction='ignore')
        if not exists:
            w.writeheader()
        data["timestamp"] = datetime.now(timezone.utc).isoformat()
        w.writerow(data)
    logger.info(f"Trade logged: {data.get('symbol')} {data.get('direction')} @ {data.get('entry')}")


def scan_closed_trades() -> int:
    """
    Checks MT5 for newly closed trades, appends to closed_trades.csv,
    and triggers RL update for each.
    Returns count of new closed trades found.
    """
    if not MT5_OK:
        return 0
    try:
        from datetime import timedelta
        from intelligence.rl_agent import update as rl_update

        now   = datetime.now(timezone.utc)
        since = now - timedelta(hours=1)
        deals = mt5.history_deals_get(since, now)
        if not deals:
            return 0

        new_count = 0
        seen = _load_seen_tickets()

        for deal in deals:
            if deal.ticket in seen:
                continue
            if deal.entry != mt5.DEAL_ENTRY_OUT:
                continue

            pnl = deal.profit
            seen.add(deal.ticket)
            new_count += 1

            # Write to closed trades log
            row = {
                "ticket":    deal.ticket,
                "symbol":    deal.symbol,
                "pnl":       pnl,
                "volume":    deal.volume,
                "timestamp": datetime.fromtimestamp(deal.time, tz=timezone.utc).isoformat(),
            }
            _append_closed(row)

            # RL feedback (we don't have state here — use defaults)
            # Production: store state at entry, look up by ticket
            rl_update("UNKNOWN", "EQUILIBRIUM", "TREND_HEALTHY", 30,
                      "BUY" if deal.type == mt5.DEAL_TYPE_BUY else "SELL",
                      approved=True, pnl=pnl)

        _save_seen_tickets(seen)
        return new_count

    except Exception as e:
        logger.warning(f"scan_closed_trades error: {e}")
        return 0


def _load_seen_tickets() -> set:
    path = ".seen_tickets.txt"
    if not os.path.exists(path):
        return set()
    with open(path) as f:
        return set(int(x.strip()) for x in f if x.strip().isdigit())


def _save_seen_tickets(seen: set):
    with open(".seen_tickets.txt", 'w') as f:
        f.write("\n".join(str(t) for t in seen))


def _append_closed(row: dict):
    exists = os.path.exists(CLOSED_FILE)
    with open(CLOSED_FILE, 'a', newline='') as f:
        w = csv.DictWriter(f, fieldnames=row.keys(), extrasaction='ignore')
        if not exists:
            w.writeheader()
        w.writerow(row)
