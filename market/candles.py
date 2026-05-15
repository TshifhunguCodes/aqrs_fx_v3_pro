"""
Indicator Engine V3
Native pandas implementation for EMA, ATR, RSI, MACD, Bollinger Bands,
ADX/DI, stochastic, and momentum. This avoids import-time hangs from
third-party TA packages while keeping the same column contract.
"""
import numpy as np
import pandas as pd


def _ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def _true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    return pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for length in [8, 21, 50, 200]:
        df[f"ema{length}"] = _ema(df["close"], length)

    tr = _true_range(df)
    df["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rs = gain / (loss + 1e-12)
    df["rsi"] = 100 - (100 / (1 + rs))

    ema12 = _ema(df["close"], 12)
    ema26 = _ema(df["close"], 26)
    df["macd"] = ema12 - ema26
    df["macd_signal"] = _ema(df["macd"], 9)
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    bb_mid = df["close"].rolling(20).mean()
    bb_std = df["close"].rolling(20).std()
    df["bb_upper"] = bb_mid + (2 * bb_std)
    df["bb_mid"] = bb_mid
    df["bb_lower"] = bb_mid - (2 * bb_std)
    df["bb_pct"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"] + 1e-9)

    up_move = df["high"].diff()
    down_move = -df["low"].diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    atr = df["atr"] + 1e-12
    df["dmp"] = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1 / 14, adjust=False).mean() / atr
    df["dmn"] = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / 14, adjust=False).mean() / atr
    dx = 100 * (df["dmp"] - df["dmn"]).abs() / (df["dmp"] + df["dmn"] + 1e-12)
    df["adx"] = dx.ewm(alpha=1 / 14, adjust=False).mean()

    low14 = df["low"].rolling(14).min()
    high14 = df["high"].rolling(14).max()
    df["stoch_k"] = 100 * (df["close"] - low14) / (high14 - low14 + 1e-12)
    df["stoch_d"] = df["stoch_k"].rolling(3).mean()

    df["momentum"] = df["close"].diff(10)

    return df.bfill().ffill()


def merge_htf_context(df_m5: pd.DataFrame, df_h1: pd.DataFrame) -> pd.DataFrame:
    """
    Align H1 context to M5 candles using merge_asof (backward fill).
    H1 columns get '_h1' suffix.
    """
    df_h1 = df_h1.copy()
    df_h1.columns = [f"{c}_h1" if c != "time" else "time" for c in df_h1.columns]

    df_m5 = df_m5.sort_values("time")
    df_h1 = df_h1.sort_values("time")

    return pd.merge_asof(
        df_m5,
        df_h1[
            [
                "time",
                "close_h1",
                "ema8_h1",
                "ema21_h1",
                "ema50_h1",
                "ema200_h1",
                "rsi_h1",
                "atr_h1",
                "adx_h1",
                "macd_h1",
                "macd_signal_h1",
            ]
        ],
        on="time",
        direction="backward",
    )
