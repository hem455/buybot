@echo off
:: =================================================
:: 🔧 Chirp Trading System - メンテナンスツール
:: =================================================
setlocal enabledelayedexpansion
color 0B

echo.
echo ████████████████████████████████████████████████████████████
echo ██                                                        ██
echo ██        🔧 Chirp Trading System - メンテナンス          ██
echo ██                                                        ██
echo ████████████████████████████████████████████████████████████
echo.

:MENU
echo.
echo 📋 メニューを選択してください:
echo.
echo [1] 💊 システム健全性チェック
echo [2] 📦 依存関係の更新
echo [3] 🧹 キャッシュクリア
echo [4] 📊 ログファイル整理
echo [5] 🔄 設定ファイルのリセット
echo [6] 🌐 ポート8502のプロセス終了
echo [7] 🚀 UIを起動
echo [8] 🚪 終了
echo.
set /p choice="選択 (1-8): "

if "%choice%"=="1" goto HEALTH_CHECK
if "%choice%"=="2" goto UPDATE_DEPS
if "%choice%"=="3" goto CLEAR_CACHE
if "%choice%"=="4" goto CLEAN_LOGS
if "%choice%"=="5" goto RESET_CONFIG
if "%choice%"=="6" goto KILL_PORT
if "%choice%"=="7" goto START_UI
if "%choice%"=="8" goto END
echo ❌ 無効な選択です
goto MENU

:HEALTH_CHECK
echo.
echo 💊 システム健全性チェックを実行中...
echo ====================================

:: Python環境
echo 🐍 Python環境:
python --version 2>&1
if %errorLevel% neq 0 echo ❌ Python エラー

:: 仮想環境
echo.
echo 🔧 仮想環境:
if exist "venv\Scripts\activate.bat" (
    echo ✅ 仮想環境が存在します
    call venv\Scripts\activate
    python -c "import sys; print(f'Python: {sys.executable}')"
) else (
    echo ❌ 仮想環境が見つかりません
)

:: 重要なパッケージ
echo.
echo 📦 重要なパッケージ:
python -c "import streamlit; print(f'✅ Streamlit {streamlit.__version__}')" 2>nul || echo ❌ Streamlit なし
python -c "import pandas; print(f'✅ Pandas {pandas.__version__}')" 2>nul || echo ❌ Pandas なし
python -c "import plotly; print(f'✅ Plotly {plotly.__version__}')" 2>nul || echo ❌ Plotly なし
python -c "import numpy; print(f'✅ NumPy {numpy.__version__}')" 2>nul || echo ❌ NumPy なし

:: ファイル存在確認
echo.
echo 📁 重要なファイル:
if exist "frontend\app_production.py" (echo ✅ frontend\app_production.py) else (echo ❌ frontend\app_production.py)
if exist ".streamlit\config.toml" (echo ✅ .streamlit\config.toml) else (echo ❌ .streamlit\config.toml)
if exist ".env" (echo ✅ .env) else (echo ⚠️ .env)
if exist "requirements.txt" (echo ✅ requirements.txt) else (echo ❌ requirements.txt)

:: ポート確認
echo.
echo 🌐 ポート8502:
netstat -ano | findstr :8502 >nul 2>&1
if %errorLevel% == 0 (
    echo ⚠️ ポート8502が使用中です
    netstat -ano | findstr :8502
) else (
    echo ✅ ポート8502は利用可能です
)

:: ディスク容量
echo.
echo 💾 ディスク容量:
for /f "tokens=3" %%a in ('dir /-c ^| find "bytes free"') do echo 利用可能: %%a bytes

echo.
echo ✅ 健全性チェック完了
pause
goto MENU

:UPDATE_DEPS
echo.
echo 📦 依存関係を更新中...
echo ========================

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate
    echo pip を最新版に更新中...
    python -m pip install --upgrade pip
    echo.
    echo 依存関係を更新中...
    pip install --upgrade -r requirements.txt
    echo ✅ 依存関係の更新が完了しました
) else (
    echo ❌ 仮想環境が見つかりません
)
pause
goto MENU

:CLEAR_CACHE
echo.
echo 🧹 キャッシュをクリア中...
echo =======================

:: Streamlitキャッシュ
if exist "%USERPROFILE%\.streamlit" (
    echo Streamlitキャッシュをクリア中...
    rmdir /s /q "%USERPROFILE%\.streamlit\cache" 2>nul
    echo ✅ Streamlitキャッシュをクリアしました
)

:: Pythonキャッシュ
echo Pythonキャッシュをクリア中...
for /r . %%d in (__pycache__) do (
    if exist "%%d" (
        rmdir /s /q "%%d" 2>nul
        echo    %%d を削除
    )
)

:: 一時ファイル
echo 一時ファイルをクリア中...
del /q *.tmp 2>nul
del /q *.temp 2>nul

echo ✅ キャッシュクリア完了
pause
goto MENU

:CLEAN_LOGS
echo.
echo 📊 ログファイルを整理中...
echo =========================

if exist "logs" (
    echo 現在のログファイル:
    dir logs\*.log 2>nul
    echo.
    echo 30日以上古いログファイルを削除しますか？ [Y/N]
    set /p clean_logs=
    if /i "!clean_logs!"=="Y" (
        forfiles /p logs /s /m *.log /d -30 /c "cmd /c del @path" 2>nul
        echo ✅ 古いログファイルを削除しました
    )
) else (
    echo ℹ️ ログディレクトリが存在しません
)
pause
goto MENU

:RESET_CONFIG
echo.
echo 🔄 設定ファイルをリセット中...
echo ============================

echo ⚠️ この操作により以下の設定がリセットされます:
echo    • .streamlit\config.toml
echo    • Streamlitの設定
echo.
echo 続行しますか？ [Y/N]
set /p reset_confirm=
if /i not "!reset_confirm!"=="Y" goto MENU

if exist ".streamlit\config.toml" (
    echo 既存の設定をバックアップ中...
    copy ".streamlit\config.toml" ".streamlit\config.toml.backup" >nul
)

echo デフォルト設定を作成中...
mkdir .streamlit 2>nul
echo [server] > .streamlit\config.toml
echo port = 8502 >> .streamlit\config.toml
echo headless = true >> .streamlit\config.toml
echo enableCORS = false >> .streamlit\config.toml
echo enableXsrfProtection = false >> .streamlit\config.toml
echo [browser] >> .streamlit\config.toml
echo gatherUsageStats = false >> .streamlit\config.toml
echo [theme] >> .streamlit\config.toml
echo primaryColor = "#ff6b35" >> .streamlit\config.toml
echo backgroundColor = "#0e1117" >> .streamlit\config.toml
echo secondaryBackgroundColor = "#1a1d24" >> .streamlit\config.toml
echo textColor = "#fafafa" >> .streamlit\config.toml
echo font = "sans serif" >> .streamlit\config.toml

echo ✅ 設定ファイルをリセットしました
echo    バックアップ: .streamlit\config.toml.backup
pause
goto MENU

:KILL_PORT
echo.
echo 🌐 ポート8502のプロセスを終了中...
echo =================================

netstat -ano | findstr :8502 >nul 2>&1
if %errorLevel% == 0 (
    echo 現在のプロセス:
    netstat -ano | findstr :8502
    echo.
    echo プロセスを終了しますか？ [Y/N]
    set /p kill_confirm=
    if /i "!kill_confirm!"=="Y" (
        for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8502') do (
            echo プロセス %%a を終了中...
            taskkill /pid %%a /f >nul 2>&1
        )
        echo ✅ ポート8502のプロセスを終了しました
    )
) else (
    echo ℹ️ ポート8502を使用しているプロセスはありません
)
pause
goto MENU

:START_UI
echo.
echo 🚀 UIを起動中...
echo ===============
call launch_chirp_ui.bat
goto MENU

:END
echo.
echo 👋 メンテナンスツールを終了します
echo お疲れ様でした！
pause
exit /b 0
