"""
Adaptive Filter — Final Intelligence Gate
Combines K-Means regime + RL agent + lifecycle into one go/no-go decision.
"""
from intelligence.unsupervised_model import predict_regime, score_modifier_for_regime
from intelligence.rl_agent import rl_approve
from core.logger import logger


def adaptive_gate(df, direction: str, pd_zone: str,
                  phase: str, confirm_score: int) -> dict:
    """
    Returns:
        approved      : bool   — final gate decision
        ml_regime     : str    — K-Means detected regime
        rl_decision   : dict   — RL approval
        score_delta   : int    — net score modifier from ML layer
        reason        : str
    """
    ml_regime    = predict_regime(df)
    regime_delta = score_modifier_for_regime(ml_regime, direction)

    rl_result = rl_approve(ml_regime, pd_zone, phase, confirm_score, direction)

    # Combined gate: both regime delta must not be catastrophic AND RL approves
    approved = rl_result["approved"] and regime_delta > -15

    reason = (
        f"ml_regime={ml_regime} | regime_delta={regime_delta:+d} | "
        f"rl={rl_result['reason']}"
    )

    logger.info(f"AdaptiveGate | dir={direction} | {reason} | approved={approved}")

    return {
        "approved":    approved,
        "ml_regime":   ml_regime,
        "rl_decision": rl_result,
        "score_delta": regime_delta,
        "reason":      reason,
    }
