@echo off
REM Streamlitを別のポートで起動するバッチファイル

echo Streamlitを起動します（ポート8080）...
cd /d "%~dp0"
streamlit run frontend\app.py --server.port 8080 --server.address localhost

pause
