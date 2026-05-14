"""
Order Blocks — Enhanced SMC
Detects institutional OBs with mitigation check and body quality filter.
"""


def _body(c):
    return abs(c['close'] - c['open'])


def _range(c):
    return c['high'] - c['low']


def detect_order_block(df):
    """Legacy bool check — kept for backwards compat with scorer."""
    candle = df.iloc[-2]
    body = _body(candle)
    rng = _range(candle)
    return body > (rng * 0.6)


def detect_ob_zones(df, lookback=60):
    """
    Scans for institutional OBs:
    - Last opposing candle before a strong displacement move
    - OB must not have been fully mitigated (price closed through it)
    Returns list of {'direction', 'top', 'bottom', 'index', 'strength'}
    """
    zones = []
    data = df.iloc[-lookback:]
    atr = df['atr'].iloc[-1]

    for i in range(1, len(data) - 2):
        c = data.iloc[i]
        c_next = data.iloc[i + 1]

        body_c = _body(c)
        body_next = _body(c_next)

        # Displacement: next candle moves strongly in one direction
        is_bullish_displacement = (
            c_next['close'] > c_next['open']
            and body_next > atr * 1.2
        )
        is_bearish_displacement = (
            c_next['close'] < c_next['open']
            and body_next > atr * 1.2
        )

        # Bullish OB: bearish candle before bullish displacement
        if c['close'] < c['open'] and is_bullish_displacement:
            zone = {
                "direction": "BULLISH",
                "bottom": c['low'],
                "top": c['open'],       # OB is the body of the bearish candle
                "index": i,
                "strength": body_next / atr,
            }
        # Bearish OB: bullish candle before bearish displacement
        elif c['close'] > c['open'] and is_bearish_displacement:
            zone = {
                "direction": "BEARISH",
                "top": c['high'],
                "bottom": c['open'],
                "index": i,
                "strength": body_next / atr,
            }
        else:
            continue

        # Mitigation: price closed fully through the OB body
        subsequent = data.iloc[i + 2:]
        if zone["direction"] == "BULLISH":
            mitigated = (subsequent['close'] < zone["bottom"]).any()
        else:
            mitigated = (subsequent['close'] > zone["top"]).any()

        if not mitigated:
            zones.append(zone)

    return zones


def price_in_ob(current_price, zones, direction):
    for z in zones:
        if z["direction"] != direction:
            continue
        if z["bottom"] <= current_price <= z["top"]:
            return True
    return False
