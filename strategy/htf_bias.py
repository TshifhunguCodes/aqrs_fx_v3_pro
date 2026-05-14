def get_bias(df):

    last = df.iloc[-1]

    bullish = (
        last['ema8'] >
        last['ema21'] >
        last['ema50'] >
        last['ema200']
    )

    bearish = (
        last['ema8'] <
        last['ema21'] <
        last['ema50'] <
        last['ema200']
    )

    if bullish:
        return "BULLISH"

    if bearish:
        return "BEARISH"

    return "RANGE"