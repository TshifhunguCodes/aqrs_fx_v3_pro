"""
Volume Profile Engine
POC, VAH, VAL, session-level volume distribution.
Identifies where institutions are accumulating/distributing.
"""
import numpy as np
import pandas as pd
from core.config import VP_BINS


def build_volume_profile(df: pd.DataFrame, bins: int = VP_BINS) -> dict:
    """
    Build a price-volume histogram from OHLCV data.
    Returns POC, VAH, VAL, and the full profile.
    """
    price_low  = df['low'].min()
    price_high = df['high'].max()

    if price_high == price_low:
        mid = price_low
        return {"poc": mid, "vah": mid, "val": mid, "profile": {}}

    edges = np.linspace(price_low, price_high, bins + 1)
    volume_by_bin = np.zeros(bins)

    for _, row in df.iterrows():
        # Distribute bar volume across price range it spans
        bar_low  = row['low']
        bar_high = row['high']
        bar_vol  = row.get('tick_volume', row.get('volume', 1))

        lo_idx = int((bar_low  - price_low) / (price_high - price_low) * bins)
        hi_idx = int((bar_high - price_low) / (price_high - price_low) * bins)
        lo_idx = max(0, min(lo_idx, bins - 1))
        hi_idx = max(0, min(hi_idx, bins - 1))

        span = hi_idx - lo_idx + 1
        volume_by_bin[lo_idx:hi_idx + 1] += bar_vol / span

    # POC = price level with maximum volume
    poc_idx = int(np.argmax(volume_by_bin))
    poc = (edges[poc_idx] + edges[poc_idx + 1]) / 2

    # Value Area = 70% of total volume centred on POC
    total_vol   = volume_by_bin.sum()
    target_vol  = total_vol * 0.70
    accumulated = volume_by_bin[poc_idx]
    lo_ptr = poc_idx
    hi_ptr = poc_idx

    while accumulated < target_vol and (lo_ptr > 0 or hi_ptr < bins - 1):
        add_lo = volume_by_bin[lo_ptr - 1] if lo_ptr > 0 else 0
        add_hi = volume_by_bin[hi_ptr + 1] if hi_ptr < bins - 1 else 0
        if add_hi >= add_lo and hi_ptr < bins - 1:
            hi_ptr += 1
            accumulated += add_hi
        elif lo_ptr > 0:
            lo_ptr -= 1
            accumulated += add_lo
        else:
            break

    val = (edges[lo_ptr] + edges[lo_ptr + 1]) / 2
    vah = (edges[hi_ptr] + edges[hi_ptr + 1]) / 2

    profile = {float((edges[i] + edges[i+1]) / 2): float(volume_by_bin[i])
               for i in range(bins)}

    return {"poc": poc, "vah": vah, "val": val, "profile": profile}


def vp_zone(current_price: float, vp: dict) -> str:
    """
    Returns price position relative to value area.
    ABOVE_VAH = supply zone, BELOW_VAL = demand zone, IN_VA = inside value area.
    """
    if not vp or "vah" not in vp:
        return "UNKNOWN"
    if current_price > vp["vah"]:
        return "ABOVE_VAH"
    if current_price < vp["val"]:
        return "BELOW_VAL"
    return "IN_VA"


def vp_near_poc(current_price: float, vp: dict, atr: float, tolerance: float = 0.5) -> bool:
    """True if price is within tolerance * ATR of POC."""
    if not vp or "poc" not in vp:
        return False
    return abs(current_price - vp["poc"]) < atr * tolerance
