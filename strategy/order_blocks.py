"""
Order block detection with displacement and mitigation checks.
"""

import pandas as pd


def _body(candle):
    return abs(candle["close"] - candle["open"])


def _range(candle):
    return candle["high"] - candle["low"]


def _is_bullish(candle):
    return candle["close"] > candle["open"]


def _is_bearish(candle):
    return candle["close"] < candle["open"]


def _fallback_atr(df):
    atr = df["atr"].iloc[-1] if "atr" in df.columns else None
    if atr is None or pd.isna(atr) or atr <= 0:
        atr = (df["high"] - df["low"]).rolling(14).mean().iloc[-1]
    return atr


def detect_order_block(df):
    """Return the most recent directional OB impulse, if present."""
    if df is None or len(df) < 3:
        return None

    setup = df.iloc[-2]
    reaction = df.iloc[-1]
    rng = _range(setup)
    if rng <= 0 or _body(setup) <= rng * 0.55:
        return None

    if _is_bearish(setup) and _is_bullish(reaction):
        return "BULLISH_OB"
    if _is_bullish(setup) and _is_bearish(reaction):
        return "BEARISH_OB"
    return None


def detect_ob_zones(df, lookback=60):
    """
    Return unmitigated institutional OB zones.
    Bullish OB: bearish candle before bullish displacement.
    Bearish OB: bullish candle before bearish displacement.
    """
    zones = []
    if df is None or len(df) < 5:
        return zones

    atr = _fallback_atr(df)
    if pd.isna(atr) or atr <= 0:
        return zones

    data = df.iloc[-lookback:]
    for i in range(1, len(data) - 2):
        candle = data.iloc[i]
        next_candle = data.iloc[i + 1]
        next_body = _body(next_candle)

        bullish_displacement = _is_bullish(next_candle) and next_body > atr * 1.2
        bearish_displacement = _is_bearish(next_candle) and next_body > atr * 1.2

        if _is_bearish(candle) and bullish_displacement:
            zone = {
                "direction": "BULLISH",
                "bottom": candle["low"],
                "top": candle["open"],
                "index": i,
                "strength": next_body / atr,
            }
        elif _is_bullish(candle) and bearish_displacement:
            zone = {
                "direction": "BEARISH",
                "bottom": candle["open"],
                "top": candle["high"],
                "index": i,
                "strength": next_body / atr,
            }
        else:
            continue

        subsequent = data.iloc[i + 2:]
        if zone["direction"] == "BULLISH":
            mitigated = (subsequent["close"] < zone["bottom"]).any()
        else:
            mitigated = (subsequent["close"] > zone["top"]).any()

        if not mitigated:
            zones.append(zone)

    return zones


def price_in_ob(current_price, zones, direction):
    for zone in zones:
        if zone["direction"] != direction:
            continue
        if zone["bottom"] <= current_price <= zone["top"]:
            return True
    return False
