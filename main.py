"""
AQRS FX Pro V3 — Main Entry Point
4 concurrent loops: signal, risk management, journal, ML retrain.
Telegram notifications integrated.
"""
import time
import threading
from datetime import datetime, timezone

from core.engine import AQRSFX
from core.logger import logger
from core.config import (
    LOOP_SIGNAL_INTERVAL, LOOP_RISK_INTERVAL,
    LOOP_JOURNAL_INTERVAL, LOOP_ML_INTERVAL,
    ML_RETRAIN_EVERY, ML_MODELS_DIR,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    TELEGRAM_ENABLED, TELEGRAM_NOTIFY_ERRORS,
)
from risk.risk_manager import manage_trailing_stops, manage_breakeven
from analytics.trade_journal import scan_closed_trades
from intelligence.unsupervised_model import train as train_kmeans

import os, glob
import pandas as pd

# ── Telegram setup ───────────────────────────────────────────────────────────
if TELEGRAM_ENABLED and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
    from notifications import configure, send
    configure(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    send(
        "🤖 <b>AQRS FX Pro V3</b>\n"
        "━━━━━━━━━━━━━━\n"
        "System starting on MetaQuotes-Demo\n"
        f"<b>Time:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )
else:
    # Stub functions if Telegram disabled
    def send(*args, **kwargs):
        pass


system = AQRSFX()


# ── Loop 1: Signal scan ───────────────────────────────────────────────────────
def signal_loop():
    logger.info("Signal loop started")
    while True:
        try:
            system.run()
        except Exception as e:
            error_msg = f"Signal loop error: {e}"
            logger.error(error_msg, exc_info=True)
            if TELEGRAM_NOTIFY_ERRORS:
                send(f"⚠️ Signal Loop Error\n<code>{e}</code>")
        time.sleep(LOOP_SIGNAL_INTERVAL)


# ── Loop 2: Risk management (trailing, breakeven) ────────────────────────────
def risk_loop():
    logger.info("Risk loop started")
    while True:
        try:
            manage_trailing_stops()
            manage_breakeven()
        except Exception as e:
            error_msg = f"Risk loop error: {e}"
            logger.error(error_msg, exc_info=True)
            if TELEGRAM_NOTIFY_ERRORS:
                send(f"⚠️ Risk Loop Error\n<code>{e}</code>")
        time.sleep(LOOP_RISK_INTERVAL)


# ── Loop 3: Trade journal (record closed trades, trigger RL update) ───────────
_closed_count = 0

def journal_loop():
    global _closed_count
    logger.info("Journal loop started")
    while True:
        try:
            new_closed = scan_closed_trades()
            _closed_count += new_closed
        except Exception as e:
            error_msg = f"Journal loop error: {e}"
            logger.error(error_msg, exc_info=True)
            if TELEGRAM_NOTIFY_ERRORS:
                send(f"⚠️ Journal Loop Error\n<code>{e}</code>")
        time.sleep(LOOP_JOURNAL_INTERVAL)


# ── Loop 4: ML retrain check ──────────────────────────────────────────────────
def ml_loop():
    logger.info("ML loop started")
    last_train_count = 0
    while True:
        try:
            if _closed_count - last_train_count >= ML_RETRAIN_EVERY:
                logger.info(f"ML retrain triggered — {_closed_count} closed trades")
                csv_files = glob.glob("trades_*.csv")
                if csv_files:
                    dfs = [pd.read_csv(f) for f in csv_files]
                    df  = pd.concat(dfs, ignore_index=True)
                    train_kmeans(df)
                    last_train_count = _closed_count
        except Exception as e:
            error_msg = f"ML loop error: {e}"
            logger.error(error_msg, exc_info=True)
            if TELEGRAM_NOTIFY_ERRORS:
                send(f"⚠️ ML Retrain Error\n<code>{e}</code>")
        time.sleep(LOOP_ML_INTERVAL)


# ── Launch ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("AQRS FX Pro V3 — Starting")
    logger.info("=" * 60)

    os.makedirs(ML_MODELS_DIR, exist_ok=True)

    threads = [
        threading.Thread(target=signal_loop,  daemon=True, name="signal"),
        threading.Thread(target=risk_loop,    daemon=True, name="risk"),
        threading.Thread(target=journal_loop, daemon=True, name="journal"),
        threading.Thread(target=ml_loop,      daemon=True, name="ml"),
    ]

    for t in threads:
        t.start()
        logger.info(f"Thread started: {t.name}")

    # Keep main thread alive
    try:
        while True:
            alive = [t.name for t in threads if t.is_alive()]
            logger.info(f"Threads alive: {alive}")
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user. Exiting...")