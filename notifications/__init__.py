"""
AQRS FX Pro V3 — Telegram Notifications
Sends real-time trade alerts and error notifications via Telegram bot.
"""
import asyncio
import threading
from typing import Optional

from core.logger import logger

# Telegram credentials (from core config)
BOT_TOKEN: Optional[str] = None
CHAT_ID: Optional[str] = None


def configure(token: str, chat_id: str):
    """Set Telegram credentials at runtime."""
    global BOT_TOKEN, CHAT_ID
    BOT_TOKEN = token
    CHAT_ID = chat_id
    logger.info("Telegram notifications configured")


def _send_sync(message: str) -> bool:
    """Send a Telegram message synchronously using requests."""
    if not BOT_TOKEN or not CHAT_ID:
        logger.warning("Telegram not configured — cannot send message")
        return False

    try:
        import requests
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
        }
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            logger.info("Telegram message sent")
            return True
        else:
            logger.warning(f"Telegram API error: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        logger.warning(f"Telegram send failed: {e}")
        return False


def send(message: str, async_send: bool = True):
    """
    Send a Telegram notification.
    If async_send=True, runs in a background thread (non-blocking).
    """
    if async_send:
        thread = threading.Thread(target=_send_sync, args=(message,), daemon=True)
        thread.start()
    else:
        _send_sync(message)


# ── Trade notification formatters ────────────────────────────────────────────

def trade_opened(symbol: str, direction: str, volume: float,
                 entry: float, sl: float, tp: float,
                 score: int, rr: float, reason: str = "") -> str:
    """Format a trade opened notification."""
    emoji = "🟢" if direction == "BUY" else "🔴"
    msg = (
        f"{emoji} <b>TRADE OPENED</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"<b>Symbol:</b> {symbol}\n"
        f"<b>Direction:</b> {direction}\n"
        f"<b>Volume:</b> {volume} lots\n"
        f"<b>Entry:</b> {entry:.5f}\n"
        f"<b>SL:</b> {sl:.5f}\n"
        f"<b>TP:</b> {tp:.5f}\n"
        f"<b>R:R:</b> {rr}\n"
        f"<b>Score:</b> {score}"
    )
    if reason:
        msg += f"\n<b>Logic:</b> {reason}"
    return msg


def trade_closed(symbol: str, direction: str, pnl: float,
                 exit_reason: str, duration_hours: float = 0) -> str:
    """Format a trade closed notification."""
    emoji = "✅" if pnl > 0 else "❌"
    pnl_str = f"+${pnl:.2f}" if pnl > 0 else f"-${abs(pnl):.2f}"
    msg = (
        f"{emoji} <b>TRADE CLOSED</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"<b>Symbol:</b> {symbol}\n"
        f"<b>Direction:</b> {direction}\n"
        f"<b>P&L:</b> {pnl_str}\n"
        f"<b>Exit:</b> {exit_reason}"
    )
    if duration_hours > 0:
        msg += f"\n<b>Duration:</b> {duration_hours:.1f}h"
    return msg


def error_alert(error_msg: str, context: str = "") -> str:
    """Format an error alert."""
    msg = (
        f"⚠️ <b>SYSTEM ALERT</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"{error_msg}"
    )
    if context:
        msg += f"\n<b>Context:</b> {context}"
    return msg


def daily_summary(trades_count: int, wins: int, losses: int,
                  total_pnl: float, win_rate: float,
                  balance: float) -> str:
    """Format a daily trading summary."""
    emoji = "📊" if total_pnl >= 0 else "📉"
    pnl_str = f"+${total_pnl:.2f}" if total_pnl > 0 else f"-${abs(total_pnl):.2f}"
    msg = (
        f"{emoji} <b>DAILY SUMMARY</b>\n"
        f"━━━━━━━━━━━━━━\n"
        f"<b>Balance:</b> ${balance:,.2f}\n"
        f"<b>Trades:</b> {trades_count}\n"
        f"<b>Wins/Losses:</b> {wins}/{losses}\n"
        f"<b>Win Rate:</b> {win_rate:.1f}%\n"
        f"<b>Daily P&L:</b> {pnl_str}"
    )
    return msg