# AQRS FX Pro V3

AQRS FX Pro V3 is a Python-based forex trading system that combines institutional order flow concepts, volume profile, market regime classification, lifecycle modeling, machine learning, and reinforcement learning gatekeeping. The project supports live trading through MetaTrader 5, historical backtesting, trade journaling, and Telegram notification integration.

## Key Features

- Live trading engine with 4 concurrent loops:
  - signal generation
  - risk management
  - closed trade journaling
  - ML retrain checks
- Historical backtesting for M5 + H1 data
- Built-in trade journal and closed-trade scanning
- Telegram notifications for system state, errors, and summaries
- Configurable risk, symbol selection, and session gating
- Support for 5 forex pairs by default
- AQRS-style ALPHA/FLOW signal resolution:
  - ALPHA owns strict high-confluence sniper trades
  - FLOW owns broader exploratory trades with reduced risk
  - a final execution gate blocks direction, indicator, trend, and premium/discount conflicts
- Currency-aware symbol suffix resolution, pip-based stop floors, and FLOW-specific ATR/RR settings

## Requirements

- Python 3.11+ (recommended)
- MetaTrader5 Python package
- pandas
- pandas_ta
- numpy
- scikit-learn

Install dependencies with:

```powershell
python -m pip install -r requirements.txt
```

## Quick Start

### Live Trading

From the project root:

```powershell
python main.py
```

This starts the full live trading system with real-time scanning, risk management, journal updates, and ML retraining logic.

### Backtesting

Run the historical backtest engine for all default forex pairs:

```powershell
python backtest/run.py --symbols EURUSD GBPUSD USDJPY USDCHF USDZAR --balance 10000
```

Backtest a single pair:

```powershell
python backtest/run.py --symbols EURUSD --balance 10000
```

### View Backtest Trades

```powershell
python show_trades.py
```

This prints the contents of `backtest_results.csv` in a readable format.

### Run Menu (Windows)

Use the interactive launcher:

```powershell
run.bat
```

## Configuration

The main system configuration is in `core/config.py`.

Important configuration options include:

- `SYMBOLS` - active symbol list for live trading
- `TIMEFRAME`, `HTF_TIMEFRAME` - chart resolutions used by the engine
- `MIN_SIGNAL_SCORE`, `MAX_OPEN_TRADES`, `MAX_DAILY_DRAWDOWN`
- `ALPHA_MIN_SCORE`, `FLOW_MIN_SCORE`, `FLOW_RISK_MULTIPLIER`, `FLOW_DAILY_LIMIT`
- `PAIR_RISK`, `MAX_SPREADS`, `PAIR_MIN_ADX`, `PAIR_MIN_SCORE`
- `PAIR_PIP_SIZE`, `PAIR_MIN_STOP_PIPS`, `SYMBOL_SUFFIXES`
- `ML_RETRAIN_EVERY`, `KMEANS_CLUSTERS`, `ML_MODELS_DIR`
- `NEWS_BLACKOUT_WINDOWS`
- `LOOP_SIGNAL_INTERVAL`, `LOOP_RISK_INTERVAL`, `LOOP_JOURNAL_INTERVAL`, `LOOP_ML_INTERVAL`
- Telegram settings: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_ENABLED`, `TELEGRAM_NOTIFY_ERRORS`, `TELEGRAM_NOTIFY_TRADES`, `TELEGRAM_NOTIFY_SUMMARY`

## Supported Symbols

Default forex symbols:

- EURUSD
- GBPUSD
- USDJPY
- USDCHF
- USDCAD

Index symbols are configured but not active by default:

- US30.cash
- NAS100.cash

## Project Structure

The repository is organized into layered components for data, strategy, risk, execution, intelligence, and utilities.

```text
aqrs_fx_v3_pro/
├── analytics/
│   └── trade_journal.py
├── backtest/
│   └── run.py
├── core/
│   ├── config.py
│   ├── engine.py
│   └── logger.py
├── execution/
│   └── entries.py
├── intelligence/
│   ├── adaptive_filter.py
│   ├── rl_agent.py
│   └── unsupervised_model.py
├── logs/
├── market/
│   ├── candles.py
│   ├── mt5_connector.py
│   └── spread.py
├── models/
├── notifications/
├── regime/
│   ├── market_lifecycle.py
│   ├── market_regime.py
│   └── volume_profile.py
├── risk/
│   ├── dynamic_exit.py
│   ├── news_guard.py
│   └── risk_manager.py
├── strategy/
│   ├── candle_confirm.py
│   ├── fvg.py
│   ├── htf_bias.py
│   ├── liquidity.py
│   ├── manipulation.py
│   ├── order_blocks.py
│   ├── scoring.py
│   ├── session.py
│   └── structure.py
├── backtest_results.csv
├── closed_trades.csv
├── main.py
├── QUICK_COMMANDS.txt
├── README.md
├── requirements.txt
├── RUN_COMMANDS.md
├── run.bat
├── run_error.txt
├── show_trades.py
├── trades_journal.csv
└── utils/
```

## Usage Notes

- Live trading requires a working MetaTrader 5 connection.
- Backtests rely on MT5 historical data access.
- Logs are written to `logs/system.log`.
- The system is designed to run continuously and will restart loops automatically if configured to do so.

## Logging and Monitoring

Monitor live logs in PowerShell:

```powershell
Get-Content .\logs\system.log -Tail 50 -Wait
```

## Troubleshooting

- Ensure `MetaTrader5` is installed and reachable from Python.
- Confirm Python can import `core.engine` successfully:

```powershell
python -c "from core.engine import AQRSFX; print('✅ System ready')"
```

- If Telegram notifications are not desired, set `TELEGRAM_ENABLED = False` in `core/config.py`.

## Development

- Adjust trading rules inside `strategy/` and `regime/` modules.
- Tune position sizing and stop/loss logic in `risk/`.
- Update machine learning behavior inside `intelligence/`.

## Disclaimer

This repository is intended for research and development. Trading forex and CFDs carries risk, and past performance is not indicative of future results. Use at your own risk.
