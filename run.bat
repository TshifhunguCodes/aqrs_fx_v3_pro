@echo off
REM AQRS FX Pro V3 - Quick Command Selector
REM Run this batch file and select which command to execute

setlocal enabledelayedexpansion
cd "c:\DEMO SYS\aqrs_fx_pro_v3"

:menu
cls
echo.
echo ========================================
echo   AQRS FX Pro V3 - Command Menu
echo ========================================
echo.
echo 1. Live Trading (Real-time, 5 forex pairs)
echo 2. Backtest All 5 Pairs
echo 3. Backtest Single Pair (EURUSD)
echo 4. View Recent Trades
echo 5. Monitor Live Logs
echo 6. Check System Status
echo 7. Exit
echo.
set /p choice="Enter your choice (1-7): "

if "%choice%"=="1" goto live
if "%choice%"=="2" goto backtest_all
if "%choice%"=="3" goto backtest_single
if "%choice%"=="4" goto view_trades
if "%choice%"=="5" goto monitor_logs
if "%choice%"=="6" goto check_status
if "%choice%"=="7" exit /b

echo Invalid choice. Please try again.
timeout /t 2 /nobreak
goto menu

:live
echo Starting live trading...
python main.py
pause
goto menu

:backtest_all
echo Starting backtest on all 5 pairs...
python backtest/run.py --symbols EURUSD GBPUSD USDJPY USDCHF USDZAR --balance 10000
pause
goto menu

:backtest_single
echo Starting backtest on EURUSD...
python backtest/run.py --symbols EURUSD --balance 10000
pause
goto menu

:view_trades
echo Displaying recent trades...
python show_trades.py
pause
goto menu

:monitor_logs
echo Showing last 50 lines of system log...
powershell -Command "Get-Content 'logs\system.log' -Tail 50"
pause
goto menu

:check_status
echo Checking system status...
python -c "from core.engine import AQRSFX; import core.config; print('✅ System Ready'); print('Symbols:', core.config.SYMBOLS)"
pause
goto menu
