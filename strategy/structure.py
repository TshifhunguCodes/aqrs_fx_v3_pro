"""
Market structure helpers for HH/HL/LH/LL, BOS/CHOCH, premium/discount,
and inducement.
"""


def _find_swing_highs(df, left=5, right=5):
    highs = []
    if len(df) < left + right + 1:
        return highs

    for i in range(left, len(df) - right):
        value = df["high"].iloc[i]
        window_high = df["high"].iloc[i - left:i + right + 1].max()
        if value == window_high and (df["high"].iloc[i - left:i] < value).all():
            highs.append((i, value))
    return highs


def _find_swing_lows(df, left=5, right=5):
    lows = []
    if len(df) < left + right + 1:
        return lows

    for i in range(left, len(df) - right):
        value = df["low"].iloc[i]
        window_low = df["low"].iloc[i - left:i + right + 1].min()
        if value == window_low and (df["low"].iloc[i - left:i] > value).all():
            lows.append((i, value))
    return lows


def _empty_structure():
    return {
        "trend": "RANGE",
        "bos": None,
        "choch": None,
        "last_sh": None,
        "last_sl": None,
        "structure_points": [],
    }


def classify_structure(df):
    """
    Return the current market structure:
    trend: BULLISH, BEARISH, or RANGE
    bos: bullish/bearish break of structure when continuing
    choch: bullish/bearish change of character against previous structure
    """
    if df is None or len(df) < 20:
        return _empty_structure()

    swing_width = 3 if len(df) < 120 else 5
    sh_list = _find_swing_highs(df, left=swing_width, right=swing_width)
    sl_list = _find_swing_lows(df, left=swing_width, right=swing_width)

    result = _empty_structure()
    if len(sh_list) < 2 or len(sl_list) < 2:
        return result

    sh1_idx, sh1 = sh_list[-2]
    sh2_idx, sh2 = sh_list[-1]
    sl1_idx, sl1 = sl_list[-2]
    sl2_idx, sl2 = sl_list[-1]

    result["last_sh"] = sh2
    result["last_sl"] = sl2
    result["structure_points"] = [
        (sh1_idx, sh1, "SH"),
        (sh2_idx, sh2, "SH"),
        (sl1_idx, sl1, "SL"),
        (sl2_idx, sl2, "SL"),
    ]

    bullish_structure = sh2 > sh1 and sl2 > sl1
    bearish_structure = sh2 < sh1 and sl2 < sl1

    if bullish_structure:
        result["trend"] = "BULLISH"
    elif bearish_structure:
        result["trend"] = "BEARISH"

    current_close = df.iloc[-1]["close"]
    broke_high = current_close > sh2
    broke_low = current_close < sl2

    if bearish_structure and broke_high:
        result["choch"] = "BULLISH_CHOCH"
    elif bullish_structure and broke_low:
        result["choch"] = "BEARISH_CHOCH"
    elif broke_high:
        result["bos"] = "BULLISH_BOS"
    elif broke_low:
        result["bos"] = "BEARISH_BOS"

    return result


def premium_discount(last_sh, last_sl, current_price):
    """
    ICT premium/discount model based on the latest confirmed swing range.
    Discount supports BUY setups; premium supports SELL setups.
    """
    if last_sh is None or last_sl is None:
        return "EQUILIBRIUM"

    high = max(last_sh, last_sl)
    low = min(last_sh, last_sl)
    rng = high - low
    if rng == 0:
        return "EQUILIBRIUM"

    position = (current_price - low) / rng
    if position < 0.45:
        return "DISCOUNT"
    if position > 0.55:
        return "PREMIUM"
    return "EQUILIBRIUM"


def detect_inducement(df, direction):
    """
    Detect a minor stop run followed by same-direction rejection.
    """
    if df is None or len(df) < 14:
        return False

    window = df.iloc[-12:-2]
    c_prev = df.iloc[-2]
    c_curr = df.iloc[-1]

    if direction == "BUY":
        minor_low = window["low"].min()
        swept = c_prev["low"] < minor_low or c_curr["low"] < minor_low
        recovered = c_curr["close"] > minor_low and c_curr["close"] > c_curr["open"]
        return bool(swept and recovered)

    minor_high = window["high"].max()
    swept = c_prev["high"] > minor_high or c_curr["high"] > minor_high
    recovered = c_curr["close"] < minor_high and c_curr["close"] < c_curr["open"]
    return bool(swept and recovered)
