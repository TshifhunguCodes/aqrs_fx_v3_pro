def classify_behavior(df, pip_size: float = 0.0001) -> dict:
    """AQRS market behavior classifier with pip-aware volatility context."""
    if df is None or len(df) < 25:
        return {"label": "RANGE", "confidence": 0, "features": {}}

    work = df.copy()
    last = work.iloc[-1]
    prev = work.iloc[-2]
    ema20 = work["close"].ewm(span=20, adjust=False).mean()
    tr = (work["high"] - work["low"]).abs()
    atr14 = tr.ewm(alpha=1 / 14, adjust=False).mean()
    range_20 = work["high"].rolling(20).max() - work["low"].rolling(20).min()
    flips = (work["close"].diff().tail(10).apply(lambda v: 1 if v > 0 else -1).diff().abs() > 0).sum()

    momentum = last["close"] - work["close"].iloc[-6]
    slope = ema20.iloc[-1] - ema20.iloc[-5]
    atr_pips = atr14.iloc[-1] / max(pip_size, 1e-12)
    avg_tr_pips = tr.tail(20).mean() / max(pip_size, 1e-12)

    trend_up = last["close"] > ema20.iloc[-1] and slope > 0 and momentum > 0
    trend_down = last["close"] < ema20.iloc[-1] and slope < 0 and momentum < 0
    breakout = last["close"] > work["high"].rolling(20).max().iloc[-2] or last["close"] < work["low"].rolling(20).min().iloc[-2]
    reversal = (prev["close"] > ema20.iloc[-2] and last["close"] < ema20.iloc[-1]) or (
        prev["close"] < ema20.iloc[-2] and last["close"] > ema20.iloc[-1]
    )
    choppy = flips >= 6 or (range_20.iloc[-1] / max(atr14.iloc[-1], 1e-12)) < 3
    volatile = atr_pips > max(avg_tr_pips * 1.6, 12)

    if trend_up:
        label = "TREND_UP"
    elif trend_down:
        label = "TREND_DOWN"
    elif breakout:
        label = "BREAKOUT"
    elif reversal:
        label = "REVERSAL"
    elif volatile:
        label = "VOLATILE"
    elif choppy:
        label = "CHOPPY"
    else:
        label = "RANGE"

    confidence = 50
    confidence += 20 if label in ("TREND_UP", "TREND_DOWN", "BREAKOUT") else 0
    confidence += 10 if abs(momentum) > atr14.iloc[-1] else 0
    confidence -= 15 if choppy else 0

    return {
        "label": label,
        "confidence": max(0, min(100, confidence)),
        "features": {
            "prev_close": prev["close"],
            "momentum": momentum,
            "ema20": ema20.iloc[-1],
            "slope": slope,
            "high_20": work["high"].rolling(20).max().iloc[-1],
            "low_20": work["low"].rolling(20).min().iloc[-1],
            "tr": tr.iloc[-1],
            "atr14": atr14.iloc[-1],
            "avg_tr_20": tr.tail(20).mean(),
            "range": range_20.iloc[-1],
            "range_mean": range_20.tail(20).mean(),
            "candle_expansion": tr.iloc[-1] / max(tr.tail(20).mean(), 1e-12),
            "volatility": atr_pips,
            "trend_up": trend_up,
            "trend_down": trend_down,
            "breakout": breakout,
            "reversal": reversal,
            "flip_count_10": int(flips),
            "choppy": choppy,
        },
    }
