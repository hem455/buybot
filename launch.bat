@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
color 0A

echo.
echo ===============================================
echo  Chirp Trading System - Production
echo ===============================================
echo.

REM Check for .env file
if not exist ".env" (
    echo ERROR: .env file not found!
    echo Please copy .env.example to .env and configure your API keys.
    echo.
    pause
    exit /b 1
)

REM Load environment variables from .env file
for /f "tokens=1,2 delims==" %%a in (.env) do (
    if not "%%a"=="" if not "%%b"=="" (
        set "%%a=%%b"
    )
)

echo Environment loaded from .env file.

REM Check virtual environment
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate
) else (
    echo Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate
    pip install -r system\requirements.txt
)

REM Production warning
echo.
echo *** WARNING: PRODUCTION MODE ***
echo This will connect to REAL GMO Coin API
echo.
echo Continue? [Y/N]
set /p confirm=
if /i not "%confirm%"=="Y" (
    exit /b 0
)

REM Kill existing process on port 8502
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8502') do (
    taskkill /pid %%a /f >nul 2>&1
)

REM Start
echo.
echo Starting system...
echo URL: http://localhost:8502
echo.
start "" "http://localhost:8502"

REM Environment variables are already loaded from .env file above

python -m streamlit run frontend/app_production.py --server.port 8502

pause
