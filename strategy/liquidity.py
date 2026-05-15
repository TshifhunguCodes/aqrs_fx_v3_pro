def liquidity_sweep(df, lookback=10):
    """
    Detect a stop run and rejection.

    BUY_SIDE_SWEEP means buy-side liquidity was taken above recent highs and
    price closed back below the pool. SELL_SIDE_SWEEP is the inverse.
    """
    if df is None or len(df) < lookback + 2:
        return None

    previous_high = df["high"].iloc[-lookback - 1:-1].max()
    previous_low = df["low"].iloc[-lookback - 1:-1].min()
    current = df.iloc[-1]

    if current["high"] > previous_high and current["close"] < previous_high:
        return "BUY_SIDE_SWEEP"

    if current["low"] < previous_low and current["close"] > previous_low:
        return "SELL_SIDE_SWEEP"

    return None


def sweep_supports_direction(sweep, direction):
    return (
        (direction == "BUY" and sweep == "SELL_SIDE_SWEEP") or
        (direction == "SELL" and sweep == "BUY_SIDE_SWEEP")
    )
