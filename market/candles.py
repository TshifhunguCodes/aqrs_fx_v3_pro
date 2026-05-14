"""
Indicator Engine V3
Rich indicator set: EMA stack, RSI, MACD, BB, ATR, ADX, Stochastic.
Supports M5 and H1 timeframes; merge_asof H1 context into M5.
"""
import pandas as pd
import pandas_ta as ta


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # EMA stack
    for n in [8, 21, 50, 200]:
        df[f'ema{n}'] = ta.ema(df['close'], length=n)

    # ATR (core for risk)
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)

    # RSI
    df['rsi'] = ta.rsi(df['close'], length=14)

    # MACD
    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    if macd is not None and not macd.empty:
        df['macd']        = macd.iloc[:, 0]
        df['macd_signal'] = macd.iloc[:, 1]
        df['macd_hist']   = macd.iloc[:, 2]

    # Bollinger Bands
    bb = ta.bbands(df['close'], length=20, std=2)
    if bb is not None and not bb.empty:
        df['bb_upper'] = bb.iloc[:, 0]
        df['bb_mid']   = bb.iloc[:, 1]
        df['bb_lower'] = bb.iloc[:, 2]
        df['bb_pct']   = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'] + 1e-9)

    # ADX + DI
    adx = ta.adx(df['high'], df['low'], df['close'], length=14)
    if adx is not None and not adx.empty:
        df['adx']  = adx.iloc[:, 0]
        df['dmp']  = adx.iloc[:, 1]
        df['dmn']  = adx.iloc[:, 2]

    # Stochastic
    stoch = ta.stoch(df['high'], df['low'], df['close'], k=14, d=3, smooth_k=3)
    if stoch is not None and not stoch.empty:
        df['stoch_k'] = stoch.iloc[:, 0]
        df['stoch_d'] = stoch.iloc[:, 1]

    # Momentum
    df['momentum'] = df['close'].diff(10)

    return df


def merge_htf_context(df_m5: pd.DataFrame, df_h1: pd.DataFrame) -> pd.DataFrame:
    """
    Align H1 context to M5 candles using merge_asof (backward fill).
    H1 columns get '_h1' suffix.
    """
    df_h1 = df_h1.copy()
    df_h1.columns = [f"{c}_h1" if c != 'time' else 'time' for c in df_h1.columns]

    df_m5 = df_m5.sort_values('time')
    df_h1 = df_h1.sort_values('time')

    merged = pd.merge_asof(
        df_m5,
        df_h1[['time', 'close_h1', 'ema8_h1', 'ema21_h1',
               'ema50_h1', 'ema200_h1', 'rsi_h1', 'atr_h1',
               'adx_h1', 'macd_h1', 'macd_signal_h1']],
        on='time',
        direction='backward'
    )
    return merged
