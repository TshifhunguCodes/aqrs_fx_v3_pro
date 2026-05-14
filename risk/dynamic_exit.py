"""
Dynamic Exit Engine
Adaptive TP/SL based on: market regime, lifecycle phase, ATR, BB position.
Replaces flat 1.5×ATR SL / 3×ATR TP with context-aware exits.
"""


def dynamic_sltp(entry: float, atr: float, direction: str,
                 regime: str = "UNKNOWN", phase: str = "TREND_HEALTHY",
                 bb_pct: float = 0.5, rr_override: float = None) -> dict:
    """
    Returns {'sl': float, 'tp': float, 'sl_dist': float,
             'tp_dist': float, 'rr': float, 'logic': str}
    """
    # Base SL multiplier — tighten in choppy/volatile, widen in healthy trend
    sl_mult = {
        "ALIGNED_TREND":   1.2,
        "TREND_MISMATCH":  1.8,
        "CHOPPY":          2.0,
        "VOLATILE":        2.5,
        "BREAKOUT":        1.3,
        "MEAN_REVERTING":  1.5,
        "UNKNOWN":         1.5,
    }.get(regime, 1.5)

    # Lifecycle modifier
    phase_mult = {
        "TREND_HEALTHY":    1.0,
        "REVERSAL_WATCH":   1.3,
        "TREND_EXHAUSTING": 1.5,
        "DISTRIBUTION":     1.4,
        "ACCUMULATION":     1.4,
        "FORCE_EXIT":       2.0,
    }.get(phase, 1.0)

    sl_dist = atr * sl_mult * phase_mult
    sl_dist = max(sl_dist, atr * 1.0)   # floor: never less than 1×ATR

    # Dynamic R:R — tighter in healthy trend, wider in uncertain conditions
    if rr_override:
        rr = rr_override
    elif phase == "TREND_HEALTHY" and regime == "ALIGNED_TREND":
        rr = 3.0
    elif regime in ("CHOPPY", "VOLATILE"):
        rr = 1.5
    else:
        rr = 2.0

    tp_dist = sl_dist * rr
    logic   = f"regime={regime} | phase={phase} | sl_mult={sl_mult:.1f}×ATR | rr={rr}"

    if direction == "BUY":
        sl = entry - sl_dist
        tp = entry + tp_dist
    else:
        sl = entry + sl_dist
        tp = entry - tp_dist

    return {
        "sl": round(sl, 5), "tp": round(tp, 5),
        "sl_dist": sl_dist, "tp_dist": tp_dist,
        "rr": rr, "logic": logic
    }


def breakeven_level(entry: float, sl: float, direction: str,
                    trigger_rr: float = 1.0) -> float:
    """Price level at which to move SL to breakeven."""
    dist = abs(entry - sl)
    if direction == "BUY":
        return entry + dist * trigger_rr
    return entry - dist * trigger_rr
