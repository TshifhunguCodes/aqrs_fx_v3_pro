from core.config import FLOW_MIN_SCORE, FLOW_ATR_SL_MULTIPLIERS, FLOW_RR_RATIOS


def _flow_type(context: dict) -> str:
    direction = context["direction"]
    lifecycle_phase = context["lifecycle"].get("phase")
    structure = context["structure"]
    pd_zone = context.get("pd_zone")
    liquidity = context.get("liquidity")

    if lifecycle_phase == "REVERSAL_WATCH" and (structure.get("choch") or liquidity):
        return "EARLY_REVERSAL_ENTRY"
    if lifecycle_phase == "TREND_EXHAUSTING" and liquidity:
        return "EXHAUSTION_FADE"
    if (direction == "BUY" and pd_zone == "DISCOUNT") or (direction == "SELL" and pd_zone == "PREMIUM"):
        return "MICRO_RETRACEMENT_REENTRY"
    return "MOMENTUM_CONTINUATION"


def generate_flow_setup(score: int, context: dict) -> dict:
    """Broader exploratory setup with lower risk and explicit setup metadata."""
    direction = context["direction"]
    indicators = context["indicators"]
    trade_type = _flow_type(context)
    counter_trend = not context.get("mtf_aligned", False)
    reversal_evidence = bool(context["structure"].get("choch") or context.get("liquidity") or context["structure"].get("bos"))

    allowed = (
        score >= FLOW_MIN_SCORE
        and indicators["score"] >= 20
        and not indicators["strong_conflict"]
        and context["lifecycle"].get("allow_new_entry", True)
    )
    if counter_trend and not (trade_type in ("EXHAUSTION_FADE", "EARLY_REVERSAL_ENTRY") and reversal_evidence):
        allowed = False

    return {
        "flow_signal": "FLOW_TRADE" if allowed else "NO_TRADE",
        "flow_score": score if allowed else 0,
        "flow_direction": "LONG" if allowed and direction == "BUY" else "SHORT" if allowed else None,
        "flow_trade_type": trade_type if allowed else "NONE",
        "flow_counter_trend_allowed": bool(counter_trend and allowed),
        "flow_atr_sl_multiplier": FLOW_ATR_SL_MULTIPLIERS.get(trade_type, 1.8),
        "flow_rr_ratio": FLOW_RR_RATIOS.get(trade_type, 1.5),
        "flow_signal_expiry_minutes": 10,
        "flow_max_open_trades": 1,
        "flow_indicator_score": indicators["score"],
        "flow_indicator_confirmations": ",".join(indicators["confirmations"]),
        "flow_indicator_conflict": ",".join(indicators["conflicts"]),
    }
