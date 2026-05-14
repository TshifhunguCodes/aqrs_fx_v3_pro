"""
Reinforcement Learning Agent — Q-Learning
Learns from closed trade P&L outcomes to approve / reject signals.
State = (regime, pd_zone, lifecycle_phase, confirm_tier)
Action = APPROVE (1) | REJECT (0)
"""
import os
import pickle
import random
import numpy as np
from core.config import RL_ALPHA, RL_GAMMA, RL_EPSILON_START, RL_EPSILON_MIN, ML_MODELS_DIR
from core.logger import logger

Q_PATH  = os.path.join(ML_MODELS_DIR, "rl_qtable.pkl")
EP_PATH = os.path.join(ML_MODELS_DIR, "rl_epsilon.pkl")
os.makedirs(ML_MODELS_DIR, exist_ok=True)

REGIMES   = ["BULL", "BEAR", "SIDEWAYS", "VOLATILE", "UNKNOWN", "UNTRAINED"]
PD_ZONES  = ["DISCOUNT", "PREMIUM", "EQUILIBRIUM"]
PHASES    = ["TREND_HEALTHY", "REVERSAL_WATCH", "TREND_EXHAUSTING",
             "DISTRIBUTION", "ACCUMULATION", "FORCE_EXIT"]
CONFIRM_TIERS = ["STRONG", "MODERATE", "WEAK"]  # based on confirm score


def _confirm_tier(confirm_score: int) -> str:
    if confirm_score >= 50: return "STRONG"
    if confirm_score >= 25: return "MODERATE"
    return "WEAK"


def _state_key(regime, pd_zone, phase, confirm_score, direction) -> tuple:
    return (regime, pd_zone, phase, _confirm_tier(confirm_score), direction)


def _load():
    try:
        with open(Q_PATH,  'rb') as f: q = pickle.load(f)
        with open(EP_PATH, 'rb') as f: e = pickle.load(f)
        return q, e
    except Exception:
        return {}, RL_EPSILON_START


def _save(q, epsilon):
    with open(Q_PATH,  'wb') as f: pickle.dump(q, f)
    with open(EP_PATH, 'wb') as f: pickle.dump(epsilon, f)


def should_take_trade(regime: str, pd_zone: str, phase: str,
                      confirm_score: int, direction: str) -> bool:
    """
    ε-greedy action selection.
    Returns True (APPROVE) or False (REJECT).
    """
    q, epsilon = _load()
    state = _state_key(regime, pd_zone, phase, confirm_score, direction)

    if random.random() < epsilon:
        return random.choice([True, False])

    q_approve = q.get((state, 1), 0.0)
    q_reject  = q.get((state, 0), 0.0)
    return q_approve >= q_reject


def update(regime: str, pd_zone: str, phase: str, confirm_score: int,
           direction: str, approved: bool, pnl: float):
    """
    Update Q-table after trade closes.
    Reward = sign(pnl) * sqrt(abs(pnl)) to reduce variance.
    """
    q, epsilon = _load()
    state  = _state_key(regime, pd_zone, phase, confirm_score, direction)
    action = 1 if approved else 0
    reward = np.sign(pnl) * np.sqrt(abs(pnl))

    old_q   = q.get((state, action), 0.0)
    new_q   = old_q + RL_ALPHA * (reward + RL_GAMMA * max(
        q.get((state, 0), 0.0), q.get((state, 1), 0.0)
    ) - old_q)
    q[(state, action)] = new_q

    # Decay epsilon
    epsilon = max(RL_EPSILON_MIN, epsilon * 0.995)

    _save(q, epsilon)
    logger.info(f"RL update | state={state} | action={action} | "
                f"reward={reward:.3f} | new_q={new_q:.3f} | ε={epsilon:.3f}")


def rl_approve(regime: str, pd_zone: str, phase: str,
               confirm_score: int, direction: str) -> dict:
    """
    Returns approval decision + metadata.
    If Q-table is empty (no trades yet), defaults to APPROVE.
    """
    q, _ = _load()
    if not q:
        return {"approved": True, "reason": "NO_HISTORY_YET"}

    approved = should_take_trade(regime, pd_zone, phase, confirm_score, direction)
    return {
        "approved": approved,
        "reason": "RL_APPROVE" if approved else "RL_REJECT"
    }
