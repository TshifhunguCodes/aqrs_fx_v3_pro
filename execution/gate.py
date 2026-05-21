from core.config import FLOW_DAILY_LIMIT


def _is_reversal_allowed(structure: dict, liquidity, candle_confirm: dict) -> bool:
    return bool(
        structure.get("choch")
        or structure.get("bos")
        or liquidity
        or candle_confirm.get("score", 0) >= 30
    )


def execution_gate(context: dict, resolved: dict, open_flow_trades_today: int = 0) -> dict:
    """Final AQRS safety gate before order construction."""
    if resolved["signal"] == "NO_TRADE" or resolved["direction"] not in ("BUY", "SELL"):
        return {"approved": False, "reason": "NO_VALID_SIGNAL"}

    direction = resolved["direction"]
    behavior = context.get("behavior_label")
    structure = context["structure"]
    indicators = context["indicators"]
    pd_zone = context.get("pd_zone")

    if direction == "SELL" and behavior == "TREND_UP" and not _is_reversal_allowed(structure, context.get("liquidity"), context["candle_confirm"]):
        return {"approved": False, "reason": "BLOCK_SELL_IN_TREND_UP"}
    if direction == "BUY" and behavior == "TREND_DOWN" and not _is_reversal_allowed(structure, context.get("liquidity"), context["candle_confirm"]):
        return {"approved": False, "reason": "BLOCK_BUY_IN_TREND_DOWN"}
    if indicators["strong_conflict"] and not _is_reversal_allowed(structure, context.get("liquidity"), context["candle_confirm"]):
        return {"approved": False, "reason": "INDICATOR_TAPE_CONFLICT"}
    if direction == "BUY" and pd_zone == "PREMIUM" and resolved["signal_owner"] == "FLOW" and not context.get("price_in_fvg"):
        return {"approved": False, "reason": "FLOW_BUY_IN_PREMIUM"}
    if direction == "SELL" and pd_zone == "DISCOUNT" and resolved["signal_owner"] == "FLOW" and not context.get("price_in_fvg"):
        return {"approved": False, "reason": "FLOW_SELL_IN_DISCOUNT"}
    if resolved["signal_owner"] == "FLOW" and open_flow_trades_today >= FLOW_DAILY_LIMIT:
        return {"approved": False, "reason": "FLOW_DAILY_LIMIT"}

    return {"approved": True, "reason": "APPROVED"}
