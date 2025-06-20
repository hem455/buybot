@echo off
echo ==========================================
echo GMO Coin Trading System - Data Download
echo ==========================================
echo.

REM Activate virtual environment
call venv\Scripts\activate

echo Downloading cryptocurrency data...
echo.

REM Download BTC and ETH data
python download_data_multi.py --symbols BTC_JPY ETH_JPY --intervals 1hour 1day --days 180

echo.
echo =====================================
echo Additional data download examples:
echo =====================================
echo.
echo Example 1: Add XRP
echo python download_data_multi.py --symbols XRP_JPY --intervals 1hour
echo.
echo Example 2: All major currencies
echo python download_data_multi.py --symbols BTC_JPY ETH_JPY XRP_JPY LTC_JPY BCH_JPY --intervals 15min 1hour 4hour 1day
echo.
pause
