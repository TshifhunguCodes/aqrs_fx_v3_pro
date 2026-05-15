def get_bias(df):
    """
    Higher-timeframe directional bias.

    Uses EMA structure first, then confirms with DI/ADX when available. The
    full 8/21/50/200 stack is ideal, but a strong 21/50 trend with price on the
    right side of EMA50 is enough to avoid over-filtering active markets.
    """
    if df is None or len(df) < 1:
        return "RANGE"

    last = df.iloc[-1]
    close = last.get("close", 0)
    ema8 = last.get("ema8", 0)
    ema21 = last.get("ema21", 0)
    ema50 = last.get("ema50", 0)
    ema200 = last.get("ema200", 0)
    adx = last.get("adx", 0)
    dmp = last.get("dmp", 0)
    dmn = last.get("dmn", 0)

    bullish_stack = ema8 > ema21 > ema50 and close > ema50
    bearish_stack = ema8 < ema21 < ema50 and close < ema50

    bullish_long_filter = ema50 >= ema200 or close > ema200
    bearish_long_filter = ema50 <= ema200 or close < ema200

    directional_strength = adx >= 18
    bullish_di = dmp >= dmn or not directional_strength
    bearish_di = dmn >= dmp or not directional_strength

    if bullish_stack and bullish_long_filter and bullish_di:
        return "BULLISH"
    if bearish_stack and bearish_long_filter and bearish_di:
        return "BEARISH"
    return "RANGE"
