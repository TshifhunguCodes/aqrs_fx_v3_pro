"""
Unsupervised Regime Model — K-Means
Clusters market conditions into bull / bear / sideways / volatile regimes.
Auto-retrains every N closed trades.
"""
import os
import pickle
import numpy as np
import pandas as pd
from datetime import datetime

try:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False

from core.config import KMEANS_CLUSTERS, ML_MODELS_DIR
from core.logger import logger

MODEL_PATH   = os.path.join(ML_MODELS_DIR, "kmeans_regime.pkl")
SCALER_PATH  = os.path.join(ML_MODELS_DIR, "kmeans_scaler.pkl")
LABEL_PATH   = os.path.join(ML_MODELS_DIR, "kmeans_labels.pkl")
os.makedirs(ML_MODELS_DIR, exist_ok=True)

REGIME_LABELS = {0: "BULL", 1: "BEAR", 2: "SIDEWAYS", 3: "VOLATILE"}

FEATURE_COLS = [
    'rsi', 'adx', 'macd_hist', 'bb_pct', 'momentum',
    'atr', 'stoch_k', 'stoch_d'
]


def _extract_features(df: pd.DataFrame) -> np.ndarray:
    cols = [c for c in FEATURE_COLS if c in df.columns]
    X = df[cols].dropna().values
    return X


def train(df: pd.DataFrame) -> bool:
    if not SKLEARN_OK:
        logger.warning("scikit-learn not installed — K-Means disabled")
        return False

    X = _extract_features(df)
    if len(X) < KMEANS_CLUSTERS * 10:
        logger.warning("Not enough data to train K-Means")
        return False

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    km = KMeans(n_clusters=KMEANS_CLUSTERS, random_state=42, n_init=10)
    km.fit(X_scaled)

    # Auto-label clusters by centroid RSI (high RSI = bull, low = bear, mid = sideways)
    rsi_idx = FEATURE_COLS.index('rsi') if 'rsi' in FEATURE_COLS else 0
    centroids_rsi = km.cluster_centers_[:, rsi_idx]
    sorted_clusters = np.argsort(centroids_rsi)
    label_map = {}
    # lowest RSI → BEAR, highest → BULL, highest variance → VOLATILE, rest → SIDEWAYS
    label_map[sorted_clusters[0]] = "BEAR"
    label_map[sorted_clusters[-1]] = "BULL"
    label_map[sorted_clusters[1]] = "SIDEWAYS"
    if KMEANS_CLUSTERS >= 4:
        label_map[sorted_clusters[2]] = "VOLATILE"

    with open(MODEL_PATH,  'wb') as f: pickle.dump(km, f)
    with open(SCALER_PATH, 'wb') as f: pickle.dump(scaler, f)
    with open(LABEL_PATH,  'wb') as f: pickle.dump(label_map, f)

    logger.info(f"K-Means trained on {len(X)} samples | clusters={KMEANS_CLUSTERS}")
    return True


def predict_regime(df: pd.DataFrame) -> str:
    """Returns regime label for latest bar. Falls back to 'UNKNOWN'."""
    if not SKLEARN_OK:
        return "UNKNOWN"

    if not all(os.path.exists(p) for p in [MODEL_PATH, SCALER_PATH, LABEL_PATH]):
        return "UNTRAINED"

    try:
        with open(MODEL_PATH,  'rb') as f: km      = pickle.load(f)
        with open(SCALER_PATH, 'rb') as f: scaler  = pickle.load(f)
        with open(LABEL_PATH,  'rb') as f: lmap    = pickle.load(f)

        cols = [c for c in FEATURE_COLS if c in df.columns]
        row  = df[cols].dropna().iloc[-1:].values
        if len(row) == 0:
            return "UNKNOWN"

        scaled  = scaler.transform(row)
        cluster = int(km.predict(scaled)[0])
        return lmap.get(cluster, "UNKNOWN")

    except Exception as e:
        logger.warning(f"K-Means predict error: {e}")
        return "UNKNOWN"


def score_modifier_for_regime(regime: str, direction: str) -> int:
    """Returns score delta based on ML-detected regime."""
    mapping = {
        ("BULL",     "BUY"):  +10,
        ("BULL",     "SELL"): -15,
        ("BEAR",     "SELL"): +10,
        ("BEAR",     "BUY"):  -15,
        ("SIDEWAYS", "BUY"):   -5,
        ("SIDEWAYS", "SELL"):  -5,
        ("VOLATILE", "BUY"):  -10,
        ("VOLATILE", "SELL"): -10,
    }
    return mapping.get((regime, direction), 0)
