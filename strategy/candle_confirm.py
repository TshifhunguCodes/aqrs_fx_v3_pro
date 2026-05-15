"""
Candle Confirmation Engine — SMC/ICT
Validates entry with displacement, engulfing, and rejection patterns.
Entry is only valid when at least one confirmation fires.
"""


def _body(c):
    return abs(c['close'] - c['open'])


def _range(c):
    return c['high'] - c['low']


def _upper_wick(c):
    return c['high'] - max(c['open'], c['close'])


def _lower_wick(c):
    return min(c['open'], c['close']) - c['low']


def _is_bullish(c):
    return c['close'] > c['open']


def _is_bearish(c):
    return c['close'] < c['open']


# ── Displacement (strong directional candle leaving a gap/FVG) ──────────────
def displacement_candle(df, direction):
    """
    A displacement candle has:
    - Body > 60% of range
    - Body > 1.5x ATR
    - Direction matches signal
    """
    if df is None or len(df) < 1:
        return False
    c = df.iloc[-1]
    atr = df['atr'].iloc[-1]
    body = _body(c)
    rng = _range(c)

    if rng == 0:
        return False

    strong_body = body > rng * 0.60
    above_atr = body > atr * 1.5

    if direction == "BUY":
        return strong_body and above_atr and _is_bullish(c)
    return strong_body and above_atr and _is_bearish(c)


# ── Engulfing confirmation ───────────────────────────────────────────────────
def engulfing_candle(df, direction):
    """
    Current candle body fully engulfs previous candle body.
    """
    if df is None or len(df) < 2:
        return False
    prev = df.iloc[-2]
    curr = df.iloc[-1]

    prev_body_top = max(prev['open'], prev['close'])
    prev_body_bot = min(prev['open'], prev['close'])
    curr_body_top = max(curr['open'], curr['close'])
    curr_body_bot = min(curr['open'], curr['close'])

    if direction == "BUY":
        return (
            _is_bullish(curr)
            and _is_bearish(prev)
            and curr_body_top > prev_body_top
            and curr_body_bot < prev_body_bot
        )
    return (
        _is_bearish(curr)
        and _is_bullish(prev)
        and curr_body_bot < prev_body_bot
        and curr_body_top > prev_body_top
    )


# ── Rejection / Pin Bar ──────────────────────────────────────────────────────
def rejection_candle(df, direction):
    """
    Long wick rejecting price away — hammer (BUY) or shooting star (SELL).
    Wick must be >= 2x body and >= 60% of total range.
    """
    if df is None or len(df) < 1:
        return False
    c = df.iloc[-1]
    body = _body(c)
    rng = _range(c)

    if rng == 0 or body == 0:
        return False

    if direction == "BUY":
        lw = _lower_wick(c)
        return lw >= body * 2 and lw >= rng * 0.60

    uw = _upper_wick(c)
    return uw >= body * 2 and uw >= rng * 0.60


# ── Inside Bar Break (volatility compression + breakout) ────────────────────
def inside_bar_breakout(df, direction):
    """
    Previous candle is an inside bar; current breaks out in signal direction.
    """
    if df is None or len(df) < 3:
        return False
    mother = df.iloc[-3]
    inside = df.iloc[-2]
    curr = df.iloc[-1]

    # Confirm inside bar
    if not (inside['high'] < mother['high'] and inside['low'] > mother['low']):
        return False

    if direction == "BUY":
        return curr['close'] > mother['high']
    return curr['close'] < mother['low']


# ── SMC Mitigation Candle (touch + reaction off OB/FVG) ─────────────────────
def mitigation_reaction(df, direction):
    """
    Checks if price tapped a zone (wick) but closed back away from it —
    the classic SMC mitigation confirmation.
    """
    if df is None or len(df) < 2:
        return False
    c = df.iloc[-1]
    prev = df.iloc[-2]
    body = _body(c)
    if body == 0:
        return False

    if direction == "BUY":
        # Wick down (tested support) but closed bullish and above prev low
        return (
            _lower_wick(c) > body * 1.5
            and _is_bullish(c)
            and c['close'] > prev['close']
        )
    # Wick up (tested resistance) but closed bearish and below prev high
    return (
        _upper_wick(c) > body * 1.5
        and _is_bearish(c)
        and c['close'] < prev['close']
    )


# ── Master confirmation gate ─────────────────────────────────────────────────
def get_candle_confirmation(df, direction):
    """
    Returns a dict of all fired confirmations and a composite score.
    At least one confirmation is required to allow entry.
    """
    checks = {
        "displacement":     displacement_candle(df, direction),
        "engulfing":        engulfing_candle(df, direction),
        "rejection":        rejection_candle(df, direction),
        "inside_breakout":  inside_bar_breakout(df, direction),
        "mitigation":       mitigation_reaction(df, direction),
    }

    # Weight each confirmation type
    weights = {
        "displacement":    35,
        "engulfing":       25,
        "rejection":       20,
        "inside_breakout": 15,
        "mitigation":      30,
    }

    score = sum(weights[k] for k, v in checks.items() if v)
    confirmed = any(checks.values())

    return {
        "confirmed": confirmed,
        "score":     score,
        "details":   checks,
    }
