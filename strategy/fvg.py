"""
Fair value gap detection and mitigation checks.
"""


def _body(candle):
    return abs(candle["close"] - candle["open"])


def _range(candle):
    return candle["high"] - candle["low"]


def _has_displacement(candle, min_body_ratio=0.5):
    rng = _range(candle)
    return rng > 0 and _body(candle) >= rng * min_body_ratio


def detect_fvg(df):
    if df is None or len(df) < 3:
        return None

    c1 = df.iloc[-3]
    c2 = df.iloc[-2]
    c3 = df.iloc[-1]

    if not _has_displacement(c2):
        return None

    if c1["high"] < c3["low"]:
        return "BULLISH_FVG"
    if c1["low"] > c3["high"]:
        return "BEARISH_FVG"
    return None


def detect_fvg_zones(df, lookback=50):
    """
    Return unmitigated FVG zones.
    A full mitigation requires trading through the far side of the imbalance.
    """
    zones = []
    if df is None or len(df) < 5:
        return zones

    data = df.iloc[-lookback:]
    for i in range(2, len(data) - 1):
        c1 = data.iloc[i - 2]
        c2 = data.iloc[i - 1]
        c3 = data.iloc[i]

        if not _has_displacement(c2):
            continue

        if c1["high"] < c3["low"]:
            zone = {"direction": "BULLISH", "bottom": c1["high"], "top": c3["low"], "index": i}
        elif c1["low"] > c3["high"]:
            zone = {"direction": "BEARISH", "bottom": c3["high"], "top": c1["low"], "index": i}
        else:
            continue

        subsequent = data.iloc[i + 1:]
        if zone["direction"] == "BULLISH":
            mitigated = (subsequent["low"] <= zone["bottom"]).any()
        else:
            mitigated = (subsequent["high"] >= zone["top"]).any()

        if not mitigated:
            zones.append(zone)

    return zones


def price_in_fvg(current_price, zones, direction):
    for zone in zones:
        if zone["direction"] != direction:
            continue
        if zone["bottom"] <= current_price <= zone["top"]:
            return True
    return False
