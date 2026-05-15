"""
Signal Scoring Engine — V3 (Full Confluence)
Candle confirmation = hard gate.
ML regime + lifecycle modifiers applied on top of base score.
Max theoretical score ~175 → normalised to 0-100 before threshold check.
"""


def calculate_score(data: dict) -> int:
    """
    Required keys:
        bias, structure_trend, bos, choch, liquidity, fvg, ob,
        price_in_fvg, price_in_ob, manipulation, candle_confirm,
        premium_discount, inducement, valid_session, direction,
        lifecycle_modifier (int), regime_modifier (int),
        ml_regime (str), vp_zone (str), near_poc (bool),
        mtf_aligned (bool), adx (float), macd_aligned (bool)
    """
    # ── Hard gate ────────────────────────────────────────────────────────────
    if not data.get("candle_confirm", {}).get("confirmed", False):
        return 0

    # Force exit from lifecycle overrides everything
    if data.get("lifecycle_modifier", 0) <= -999:
        return 0

    score = 0
    direction = data.get("direction", "BUY")

    # ── HTF bias (20) ─────────────────────────────────────────────────────────
    bias = data.get("bias", "RANGE")
    if bias != "RANGE":
        if (direction == "BUY" and bias == "BULLISH") or \
           (direction == "SELL" and bias == "BEARISH"):
            score += 20

    # ── Structure trend (15) ──────────────────────────────────────────────────
    struct = data.get("structure_trend", "RANGE")
    if struct != "RANGE":
        if (direction == "BUY" and struct == "BULLISH") or \
           (direction == "SELL" and struct == "BEARISH"):
            score += 15

    # ── MTF alignment (10) ────────────────────────────────────────────────────
    if data.get("mtf_aligned"):
        score += 10

    # ── BOS (12) / CHOCH (15) ─────────────────────────────────────────────────
    bos   = data.get("bos")
    choch = data.get("choch")
    if bos and ((direction == "BUY" and "BULLISH" in bos) or
                (direction == "SELL" and "BEARISH" in bos)):
        score += 12
    if choch and ((direction == "BUY" and "BULLISH" in choch) or
                  (direction == "SELL" and "BEARISH" in choch)):
        score += 15

    # ── Liquidity sweep — correct direction (10) ──────────────────────────────
    liq = data.get("liquidity")
    if liq:
        if (direction == "BUY" and liq == "SELL_SIDE_SWEEP") or \
           (direction == "SELL" and liq == "BUY_SIDE_SWEEP"):
            score += 10

    # ── FVG (10) + in zone (+5) ───────────────────────────────────────────────
    fvg = data.get("fvg")
    if fvg and ((direction == "BUY" and fvg == "BULLISH_FVG") or
                (direction == "SELL" and fvg == "BEARISH_FVG")):
        score += 10
    if data.get("price_in_fvg"): score += 5

    # ── OB (10) + in zone (+5) ────────────────────────────────────────────────
    ob = data.get("ob")
    if ob and ((direction == "BUY" and ob == "BULLISH_OB") or
               (direction == "SELL" and ob == "BEARISH_OB")):
        score += 10
    if data.get("price_in_ob"):  score += 5

    # ── Candle confirm score (up to 35) ───────────────────────────────────────
    score += min(data.get("candle_confirm", {}).get("score", 0), 35)

    # ── Inducement (+10) ──────────────────────────────────────────────────────
    if data.get("inducement"): score += 10

    # ── Premium / Discount (±10) ─────────────────────────────────────────────
    pd_zone = data.get("premium_discount", "EQUILIBRIUM")
    if (direction == "BUY" and pd_zone == "DISCOUNT") or \
       (direction == "SELL" and pd_zone == "PREMIUM"):
        score += 10
    elif pd_zone != "EQUILIBRIUM":
        score -= 5

    # ── Volume Profile (POC/VAH/VAL) ─────────────────────────────────────────
    vp_zone = data.get("vp_zone", "UNKNOWN")
    if (direction == "BUY" and vp_zone == "BELOW_VAL") or \
       (direction == "SELL" and vp_zone == "ABOVE_VAH"):
        score += 8     # institutional zone alignment
    if data.get("near_poc"):
        score += 5     # price near highest volume node = key level

    # ── MACD alignment (5) ────────────────────────────────────────────────────
    if data.get("macd_aligned"): score += 5

    # ── ADX strength (5) ─────────────────────────────────────────────────────
    adx = data.get("adx", 0)
    if adx > 25: score += 5

    # ── Manipulation risk ─────────────────────────────────────────────────────
    manip = data.get("manipulation", 0)
    if manip < 30:  score += 5
    elif manip > 60: score -= 10

    # ── Session (±10) ────────────────────────────────────────────────────────
    if data.get("valid_session"):  score += 5
    else:                          score -= 10

    # ── ML / Regime modifiers ─────────────────────────────────────────────────
    score += data.get("regime_modifier",    0)
    score += data.get("lifecycle_modifier", 0)

    return max(score, 0)
