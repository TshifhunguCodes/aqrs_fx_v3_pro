def liquidity_sweep(df):

    previous_high = df['high'].iloc[-5:-1].max()
    previous_low = df['low'].iloc[-5:-1].min()

    current = df.iloc[-1]

    if current['high'] > previous_high:
        return "BUY_SIDE_SWEEP"

    if current['low'] < previous_low:
        return "SELL_SIDE_SWEEP"

    return None