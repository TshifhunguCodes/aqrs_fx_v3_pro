"""
Market Structure — HH / HL / LH / LL
Proper pivot-based structure detection using swing highs and lows.
Replaces the simple rolling-window BOS/CHOCH.
"""

import pandas as pd


# ── Swing pivot detection ────────────────────────────────────────────────────
def _find_swing_highs(df, left=5, right=5):
    highs = []
    for i in range(left, len(df) - right):
        window_high = df['high'].iloc[i - left: i + right + 1].max()
        if df['high'].iloc[i] == window_high:
            highs.append((i, df['high'].iloc[i]))
    return highs


def _find_swing_lows(df, left=5, right=5):
    lows = []
    for i in range(left, len(df) - right):
        window_low = df['low'].iloc[i - left: i + right + 1].min()
        if df['low'].iloc[i] == window_low:
            lows.append((i, df['low'].iloc[i]))
    return lows


# ── Structure classification ─────────────────────────────────────────────────
def classify_structure(df):
    """
    Returns: {
        "trend":   "BULLISH" | "BEARISH" | "RANGE",
        "bos":     "BULLISH_BOS" | "BEARISH_BOS" | None,
        "choch":   "BULLISH_CHOCH" | "BEARISH_CHOCH" | None,
        "last_sh": float,   # last swing high price
        "last_sl": float,   # last swing low price
        "structure_points": list of (index, price, type)
    }
    """
    sh_list = _find_swing_highs(df)
    sl_list = _find_swing_lows(df)

    result = {
        "trend":   "RANGE",
        "bos":     None,
        "choch":   None,
        "last_sh": None,
        "last_sl": None,
        "structure_points": [],
    }

    if len(sh_list) < 2 or len(sl_list) < 2:
        return result

    # Last two swing highs and lows
    sh1_idx, sh1 = sh_list[-2]
    sh2_idx, sh2 = sh_list[-1]
    sl1_idx, sl1 = sl_list[-2]
    sl2_idx, sl2 = sl_list[-1]

    result["last_sh"] = sh2
    result["last_sl"] = sl2

    result["structure_points"] = [
        (sh1_idx, sh1, "SH"), (sh2_idx, sh2, "SH"),
        (sl1_idx, sl1, "SL"), (sl2_idx, sl2, "SL"),
    ]

    current_close = df.iloc[-1]['close']

    # HH + HL = BULLISH trend
    bullish_structure = sh2 > sh1 and sl2 > sl1
    # LH + LL = BEARISH trend
    bearish_structure = sh2 < sh1 and sl2 < sl1

    if bullish_structure:
        result["trend"] = "BULLISH"
    elif bearish_structure:
        result["trend"] = "BEARISH"

    # BOS — close beyond last swing high/low (continuation)
    if current_close > sh2:
        result["bos"] = "BULLISH_BOS"
    elif current_close < sl2:
        result["bos"] = "BEARISH_BOS"

    # CHOCH — close beyond the OPPOSITE structure point (shift in character)
    if bearish_structure and current_close > sh2:
        result["choch"] = "BULLISH_CHOCH"   # was bearish, now broke above LH
    elif bullish_structure and current_close < sl2:
        result["choch"] = "BEARISH_CHOCH"   # was bullish, now broke below HL

    return result


# ── Premium / Discount zones (Fibonacci) ────────────────────────────────────
def premium_discount(last_sh, last_sl, current_price):
    """
    ICT premium/discount model.
    Equilibrium = 50% of the swing range.
    - Discount (<50%): valid for BUY setups
    - Premium (>50%): valid for SELL setups
    Returns: "DISCOUNT" | "PREMIUM" | "EQUILIBRIUM"
    """
    if last_sh is None or last_sl is None:
        return "EQUILIBRIUM"

    rng = last_sh - last_sl
    if rng == 0:
        return "EQUILIBRIUM"

    position = (current_price - last_sl) / rng

    if position < 0.45:
        return "DISCOUNT"
    if position > 0.55:
        return "PREMIUM"
    return "EQUILIBRIUM"


# ── Inducement (stop hunt before real move) ──────────────────────────────────
def detect_inducement(df, direction):
    """
    Looks for a minor level sweep (inducement) before the real displacement.
    Inducement = price briefly exceeds a recent minor high/low then rejects.
    """
    # Use last 10 candles to find minor highs/lows
    window = df.iloc[-12:-2]
    c_prev = df.iloc[-2]
    c_curr = df.iloc[-1]

    if direction == "BUY":
        minor_low = window['low'].min()
        # Price wick below minor low but closed back above
        swept = c_prev['low'] < minor_low
        recovered = c_curr['close'] > minor_low
        return swept and recovered

    minor_high = window['high'].max()
    swept = c_prev['high'] > minor_high
    recovered = c_curr['close'] < minor_high
    return swept and recovered
