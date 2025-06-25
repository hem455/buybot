@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
color 0A

echo.
echo ===============================================
echo  🚀 CHIRP Trading System - Modern UI 2024
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

REM Kill existing process on port 8503
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8503') do (
    taskkill /pid %%a /f >nul 2>&1
)

REM Start
echo.
echo Starting Modern UI...
echo URL: http://localhost:8503
echo.
echo 🌟 Features:
echo   - Glassmorphism Design
echo   - Animated Gradients  
echo   - Modern Typography
echo   - Responsive Layout
echo.
start "" "http://localhost:8503"

python -m streamlit run frontend/app_modern_ui.py --server.port 8503

pause 