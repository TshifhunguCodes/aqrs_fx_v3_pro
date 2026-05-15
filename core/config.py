"""AQRS FX Pro V3 — Master Config"""

FOREX_SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD"]
INDEX_SYMBOLS  = ["US30.cash", "NAS100.cash"]
SYMBOLS        = FOREX_SYMBOLS  # Only analyze the 5 forex pairs

TIMEFRAME     = "M5"
HTF_TIMEFRAME = "H1"

MIN_SIGNAL_SCORE   = 50
MAX_OPEN_TRADES    = 4
MAX_DAILY_DRAWDOWN = 0.04
DEFAULT_BALANCE    = 10_000

PAIR_RISK = {
    "EURUSD": 0.005, "GBPUSD": 0.004, "USDJPY": 0.003,
    "USDCHF": 0.003, "USDCAD": 0.004,
    "US30.cash": 0.010, "NAS100.cash": 0.010,
}
MAX_SPREADS = {
    "EURUSD": 20, "GBPUSD": 35, "USDJPY": 25,
    "USDCHF": 25, "USDCAD": 25,
    "US30.cash": 50, "NAS100.cash": 30,
}
TRAILING_STOP_POINTS = {
    "EURUSD": 0, "GBPUSD": 0, "USDJPY": 0, "USDCHF": 0, "USDCAD": 0,
    "US30.cash": 50, "NAS100.cash": 30,
}

PAIR_MIN_ADX = {
    "EURUSD": 18,
    "GBPUSD": 18,
    "USDJPY": 24,
    "USDCHF": 24,
    "USDCAD": 20,
}

PAIR_MIN_SCORE = {
    "EURUSD": 50,
    "GBPUSD": 50,
    "USDJPY": 65,
    "USDCHF": 65,
    "USDCAD": 55,
}

PAIR_REQUIRE_PD_ALIGNMENT = {
    "USDJPY": True,
    "USDCHF": True,
}

PAIR_REQUIRE_ZONE_OR_SWEEP = {
    "USDJPY": True,
    "USDCHF": True,
}

# ML
KMEANS_CLUSTERS   = 4
ML_RETRAIN_EVERY  = 50
RL_ALPHA          = 0.15
RL_GAMMA          = 0.90
RL_EPSILON_START  = 0.30
RL_EPSILON_MIN    = 0.05
ML_MODELS_DIR     = "models"

LIFECYCLE_RSI_EXHAUSTION = 70

# News blackout (UTC): (h_start, m_start, h_end, m_end, label)
NEWS_BLACKOUT_WINDOWS = [
    (13, 25, 14, 15, "NFP"),
    (18, 55, 19, 30, "FOMC"),
    (13, 55, 14, 15, "CPI"),
]

BLOCK_WEEKENDS = True
VP_BINS        = 50
LOOP_SIGNAL_INTERVAL  = 30
LOOP_RISK_INTERVAL    = 15
LOOP_JOURNAL_INTERVAL = 60
LOOP_ML_INTERVAL      = 3600

# Telegram notifications
# Set these via environment variables or edit directly for your bot
TELEGRAM_BOT_TOKEN = "8969205648:AAF479_F3Ty3MMXy1J6629rIJZn775fWgeY"
TELEGRAM_CHAT_ID   = "8092229916"
TELEGRAM_ENABLED   = True
TELEGRAM_NOTIFY_ERRORS   = True   # Send error alerts
TELEGRAM_NOTIFY_TRADES   = True   # Send trade open/close alerts
TELEGRAM_NOTIFY_SUMMARY  = True   # Send daily summary
