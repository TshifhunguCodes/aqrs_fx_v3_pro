# AQRS FX Pro V3 - Run Commands

## Quick Start

### 1. Live Trading (Real-time Analysis on 5 Forex Pairs)
```
cd "c:\DEMO SYS\aqrs_fx_pro_v3"
python main.py
```
✅ Analyzes: EURUSD, GBPUSD, USDJPY, USDCHF, USDZAR
- Runs 4 concurrent loops continuously
- Logs to `logs/system.log`
- Only trades during forex market hours
- Press Ctrl+C to stop

---

### 2. Backtest Historical Data
```
cd "c:\DEMO SYS\aqrs_fx_pro_v3"
python backtest/run.py --symbols EURUSD GBPUSD USDJPY USDCHF USDZAR --balance 10000
```
✅ Test all 5 pairs on historical data
- `--balance` sets starting capital (default: 10000)
- Outputs to `backtest_results.csv`
- Shows performance summary

---

### 3. Backtest Single Pair
```
cd "c:\DEMO SYS\aqrs_fx_pro_v3"
python backtest/run.py --symbols EURUSD --balance 10000
```
✅ Quick test on one pair

---

### 4. View Recent Trades
```
cd "c:\DEMO SYS\aqrs_fx_pro_v3"
python show_trades.py
```
✅ Display all trades from last backtest

---

### 5. Monitor Live Logs
```
Get-Content "c:\DEMO SYS\aqrs_fx_pro_v3\logs\system.log" -Tail 50
```
✅ Show last 50 lines of live trading log

---

### 6. Follow Live Logs in Real-time
```
Get-Content "c:\DEMO SYS\aqrs_fx_pro_v3\logs\system.log" -Tail 50 -Wait
```
✅ Stream live logs (Ctrl+C to stop)

---

### 7. Check Installation
```
cd "c:\DEMO SYS\aqrs_fx_pro_v3"
python -c "from core.engine import AQRSFX; print('✅ System ready')"
```
✅ Verify all modules load correctly

---

## Configuration Files

- **Main Config**: `core/config.py` - Edit MIN_SIGNAL_SCORE, MAX_OPEN_TRADES, etc.
- **Symbols**: `core/config.py` line 3-5 - Change which pairs to trade
- **Logs**: `logs/system.log` - View system activity

## Supported Forex Pairs (5)
- EURUSD
- GBPUSD
- USDJPY
- USDCHF
- USDZAR

## Notes
- System requires MT5 connection during live trading
- Backtest uses historical data from MT5
- All times in UTC
- Logs are appended to `logs/system.log`
