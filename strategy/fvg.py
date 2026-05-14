"""
Fair Value Gap (FVG) — Enhanced
Detects FVGs and checks if they've been mitigated (already filled).
"""


def detect_fvg(df):
    c1 = df.iloc[-3]
    c3 = df.iloc[-1]
    if c1['high'] < c3['low']:
        return "BULLISH_FVG"
    if c1['low'] > c3['high']:
        return "BEARISH_FVG"
    return None


def detect_fvg_zones(df, lookback=50):
    """
    Returns unmitigated FVG zones: list of {'direction','top','bottom','index'}.
    A zone is mitigated if price traded back through it after formation.
    """
    zones = []
    data = df.iloc[-lookback:]

    for i in range(2, len(data) - 1):
        c1 = data.iloc[i - 2]
        c3 = data.iloc[i]

        if c1['high'] < c3['low']:
            zone = {"direction": "BULLISH", "bottom": c1['high'], "top": c3['low'], "index": i}
        elif c1['low'] > c3['high']:
            zone = {"direction": "BEARISH", "top": c1['low'], "bottom": c3['high'], "index": i}
        else:
            continue

        subsequent = data.iloc[i + 1:]
        if zone["direction"] == "BULLISH":
            mitigated = (subsequent['low'] < zone["top"]).any()
        else:
            mitigated = (subsequent['high'] > zone["bottom"]).any()

        if not mitigated:
            zones.append(zone)

    return zones


def price_in_fvg(current_price, zones, direction):
    for z in zones:
        if z["direction"] != direction:
            continue
        if z["bottom"] <= current_price <= z["top"]:
            return True
    return False
