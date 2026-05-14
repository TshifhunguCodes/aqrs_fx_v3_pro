"""
Market Lifecycle Engine
Detects trend exhaustion, healthy trends, reversal warnings, force-exit states.
Prevents buying tops and selling bottoms.
"""
from core.config import LIFECYCLE_RSI_EXHAUSTION


def classify_lifecycle(df, direction: str) -> dict:
    """
    Returns:
        phase : TREND_HEALTHY | TREND_EXHAUSTING | REVERSAL_WATCH |
                DISTRIBUTION | ACCUMULATION | FORCE_EXIT
        score_modifier : int  (+/- applied to signal score)
        allow_new_entry: bool
    """
    last  = df.iloc[-1]
    prev  = df.iloc[-2]
    rsi   = last.get('rsi', 50)
    macd  = last.get('macd_hist', 0)
    macd_prev = prev.get('macd_hist', 0)
    adx   = last.get('adx', 20)
    bb_pct = last.get('bb_pct', 0.5)
    momentum = last.get('momentum', 0)

    # ── Force exit: extreme readings ─────────────────────────────────────────
    if direction == "BUY" and rsi > 85:
        return {"phase": "FORCE_EXIT", "score_modifier": -999, "allow_new_entry": False}
    if direction == "SELL" and rsi < 15:
        return {"phase": "FORCE_EXIT", "score_modifier": -999, "allow_new_entry": False}

    # ── Exhaustion signals ────────────────────────────────────────────────────
    exhaustion_signals = 0

    if direction == "BUY":
        if rsi > LIFECYCLE_RSI_EXHAUSTION:        exhaustion_signals += 1
        if bb_pct > 0.90:                         exhaustion_signals += 1
        if macd < macd_prev and macd_prev > 0:    exhaustion_signals += 1  # MACD divergence
        if momentum < 0 and last['close'] > prev['close']: exhaustion_signals += 1
    else:
        if rsi < (100 - LIFECYCLE_RSI_EXHAUSTION): exhaustion_signals += 1
        if bb_pct < 0.10:                          exhaustion_signals += 1
        if macd > macd_prev and macd_prev < 0:     exhaustion_signals += 1
        if momentum > 0 and last['close'] < prev['close']:  exhaustion_signals += 1

    # ── ADX trend strength ────────────────────────────────────────────────────
    strong_trend = adx > 25
    weak_trend   = adx < 15

    if exhaustion_signals >= 3:
        return {"phase": "TREND_EXHAUSTING", "score_modifier": -20, "allow_new_entry": False}

    if exhaustion_signals == 2:
        return {"phase": "REVERSAL_WATCH", "score_modifier": -10, "allow_new_entry": True}

    if weak_trend:
        return {"phase": "DISTRIBUTION" if direction == "BUY" else "ACCUMULATION",
                "score_modifier": -5, "allow_new_entry": True}

    if strong_trend and exhaustion_signals == 0:
        return {"phase": "TREND_HEALTHY", "score_modifier": +10, "allow_new_entry": True}

    return {"phase": "TREND_HEALTHY", "score_modifier": 0, "allow_new_entry": True}
