def manipulation_score(df, symbol):

    candle = df.iloc[-1]

    body = abs(candle['close'] - candle['open'])
    wick = candle['high'] - candle['low']

    score = 0

    if wick > body * 2:
        score += 25

    if symbol == "USDZAR":
        score += 20

    if symbol == "GBPUSD":
        score += 10

    return score