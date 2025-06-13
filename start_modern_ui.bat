@echo off
echo ==========================================
echo Chirp Trading System - Modern UI with Charts
echo ==========================================
echo.

REM 仮想環境をアクティブ化
call venv\Scripts\activate

echo Starting Modern Trading UI with Advanced Charts...
echo.
echo Access the UI at:
echo http://localhost:8501
echo.
echo Press Ctrl+C to stop
echo.

REM モダンUI（完全版）を起動
python -m streamlit run frontend/app_modern_complete.py --server.port 8501 --server.address 0.0.0.0 --theme.base dark --theme.primaryColor "#ff6b35"
