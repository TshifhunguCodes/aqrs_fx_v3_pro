def manipulation_score(df, symbol):
    if df is None or len(df) < 1:
        return 0

    candle = df.iloc[-1]
    body = abs(candle["close"] - candle["open"])
    full_range = candle["high"] - candle["low"]
    upper_wick = candle["high"] - max(candle["open"], candle["close"])
    lower_wick = min(candle["open"], candle["close"]) - candle["low"]

    if full_range <= 0:
        return 0

    score = 0
    wick_ratio = (upper_wick + lower_wick) / full_range

    if body == 0 or wick_ratio > 0.70:
        score += 25
    elif wick_ratio > 0.55:
        score += 15

    # These pairs were noisy in the smoke test, so demand cleaner candles.
    if symbol in {"USDJPY", "USDCHF"}:
        score += 10

    return score
