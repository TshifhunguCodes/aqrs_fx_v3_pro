"""
Market Regime Engine
6 regimes: ALIGNED_TREND, TREND_MISMATCH, CHOPPY, VOLATILE,
           BREAKOUT, MEAN_REVERTING.
Used to gate entry and weight signals differently per regime.
"""
import pandas as pd


def classify_regime(df: pd.DataFrame, df_h1: pd.DataFrame = None) -> dict:
    """
    Returns:
        regime         : str
        score_modifier : int
        description    : str
    """
    last = df.iloc[-1]
    adx       = last.get('adx', 20)
    atr       = last.get('atr', 1)
    bb_pct    = last.get('bb_pct', 0.5)
    macd_hist = last.get('macd_hist', 0)
    rsi       = last.get('rsi', 50)

    # Volatility: ATR relative to 20-period ATR average
    atr_avg = df['atr'].rolling(20).mean().iloc[-1] if 'atr' in df.columns else atr
    relative_vol = atr / atr_avg if atr_avg > 0 else 1.0

    # MTF alignment check (if H1 provided)
    mtf_aligned = False
    if df_h1 is not None and not df_h1.empty:
        h1_last = df_h1.iloc[-1]
        m5_bull  = last.get('ema8', 0) > last.get('ema21', 0) > last.get('ema50', 0)
        h1_bull  = h1_last.get('ema8', 0) > h1_last.get('ema21', 0)
        m5_bear  = last.get('ema8', 0) < last.get('ema21', 0) < last.get('ema50', 0)
        h1_bear  = h1_last.get('ema8', 0) < h1_last.get('ema21', 0)
        mtf_aligned = (m5_bull and h1_bull) or (m5_bear and h1_bear)

    # ── Regime classification ─────────────────────────────────────────────────
    if relative_vol > 1.8:
        return {"regime": "VOLATILE", "score_modifier": -15,
                "description": "Abnormally high volatility — reduce size"}

    if adx > 25:
        if mtf_aligned:
            return {"regime": "ALIGNED_TREND", "score_modifier": +15,
                    "description": "Strong trend, M5 and H1 aligned"}
        else:
            return {"regime": "TREND_MISMATCH", "score_modifier": -10,
                    "description": "Strong trend but HTF disagrees"}

    if bb_pct > 0.85 or bb_pct < 0.15:
        return {"regime": "BREAKOUT", "score_modifier": +5,
                "description": "Price at Bollinger Band extreme — possible breakout"}

    if adx < 15 and 40 < rsi < 60:
        return {"regime": "MEAN_REVERTING", "score_modifier": -5,
                "description": "Low ADX, price near mid — choppy mean-reversion mode"}

    return {"regime": "CHOPPY", "score_modifier": -10,
            "description": "No clear trend — low-confidence environment"}
