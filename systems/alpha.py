from core.config import ALPHA_MIN_SCORE


def generate_alpha_setup(score: int, context: dict) -> dict:
    """Strict sniper setup: high confluence, aligned HTF, no noisy conflict."""
    direction = context["direction"]
    structure = context["structure"]
    indicators = context["indicators"]
    quality = "ELITE" if score >= 85 else "HIGH" if score >= 70 else "NONE"

    aligned_structure = (
        (direction == "BUY" and structure.get("trend") in ("BULLISH", "RANGE")) or
        (direction == "SELL" and structure.get("trend") in ("BEARISH", "RANGE"))
    )
    has_smc_zone = context.get("price_in_fvg") or context.get("price_in_ob") or bool(context.get("liquidity")) or context.get("inducement")
    clean_market = context["regime"].get("regime") not in ("CHOPPY", "VOLATILE")
    allowed = (
        score >= ALPHA_MIN_SCORE
        and context.get("mtf_aligned")
        and aligned_structure
        and has_smc_zone
        and indicators["score"] >= 30
        and not indicators["strong_conflict"]
        and clean_market
    )

    return {
        "alpha_signal": "ALPHA_TRADE" if allowed else "NO_TRADE",
        "alpha_score": score if allowed else 0,
        "alpha_direction": "LONG" if allowed and direction == "BUY" else "SHORT" if allowed else None,
        "alpha_notes": "strict_confluence" if allowed else "alpha_filters_not_met",
        "alpha_quality": quality if allowed else "NONE",
    }
