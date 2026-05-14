"""
News & Weekend Guard
Blocks trading during high-impact news windows and weekends.
"""
from datetime import datetime, timezone
from core.config import NEWS_BLACKOUT_WINDOWS, BLOCK_WEEKENDS


def is_news_blackout() -> tuple[bool, str]:
    """Returns (is_blocked, reason)."""
    now = datetime.now(timezone.utc)

    if BLOCK_WEEKENDS and now.weekday() >= 5:
        return True, f"WEEKEND ({now.strftime('%A')})"

    h, m = now.hour, now.minute
    current = h * 60 + m

    for (hs, ms, he, me, label) in NEWS_BLACKOUT_WINDOWS:
        start = hs * 60 + ms
        end   = he * 60 + me
        if start <= current <= end:
            return True, f"NEWS_BLACKOUT:{label}"

    return False, ""


def is_trading_allowed() -> tuple[bool, str]:
    blocked, reason = is_news_blackout()
    return not blocked, reason
