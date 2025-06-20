@echo off
:: =================================================
:: 🧪 Chirp Trading System - 動作確認テスト
:: =================================================
setlocal enabledelayedexpansion
color 0E

echo.
echo ████████████████████████████████████████████████████████████
echo ██                                                        ██
echo ██       🧪 Chirp Trading System - 動作確認テスト         ██
echo ██                                                        ██
echo ████████████████████████████████████████████████████████████
echo.

echo 📋 このテストでは以下を確認します:
echo    1. Python環境の確認
echo    2. 必要ファイルの存在チェック
echo    3. ポート8502の利用可能性
echo    4. 依存関係の確認
echo    5. 設定ファイルの妥当性
echo    6. UI起動テスト（オプション）
echo.

set "total_tests=0"
set "passed_tests=0"
set "failed_tests=0"

:: テスト1: Python環境
echo [TEST 1/6] 🐍 Python環境の確認
set /a total_tests+=1
python --version >nul 2>&1
if %errorLevel% == 0 (
    echo ✅ PASS - Python が利用可能です
    for /f "tokens=*" %%i in ('python --version') do echo    %%i
    set /a passed_tests+=1
) else (
    echo ❌ FAIL - Python が見つかりません
    set /a failed_tests+=1
)
echo.

:: テスト2: 必要ファイル
echo [TEST 2/6] 📁 必要ファイルの存在チェック
set /a total_tests+=1
set "required_files=frontend\app_modern.py .streamlit\config.toml launch_chirp_ui.bat quick_launch.bat"
set "missing_files="
set "file_check_pass=true"

for %%f in (%required_files%) do (
    if exist "%%f" (
        echo    ✅ %%f
    ) else (
        echo    ❌ %%f （見つかりません）
        set "missing_files=!missing_files! %%f"
        set "file_check_pass=false"
    )
)

if "%file_check_pass%"=="true" (
    echo ✅ PASS - 全ての必要ファイルが存在します
    set /a passed_tests+=1
) else (
    echo ❌ FAIL - 一部ファイルが見つかりません
    set /a failed_tests+=1
)
echo.

:: テスト3: ポート8502
echo [TEST 3/6] 🌐 ポート8502の利用可能性
set /a total_tests+=1
netstat -ano | findstr :8502 >nul 2>&1
if %errorLevel% == 0 (
    echo ❌ FAIL - ポート8502が使用中です
    echo    使用中のプロセス:
    netstat -ano | findstr :8502
    set /a failed_tests+=1
) else (
    echo ✅ PASS - ポート8502は利用可能です
    set /a passed_tests+=1
)
echo.

:: テスト4: 依存関係
echo [TEST 4/6] 📦 依存関係の確認
set /a total_tests+=1

:: 仮想環境がある場合はアクティベート
if exist "venv\Scripts\activate.bat" (
    echo    仮想環境を一時的にアクティベート中...
    call venv\Scripts\activate
)

set "dependency_check_pass=true"
set "required_packages=streamlit pandas plotly numpy"

for %%p in (%required_packages%) do (
    python -c "import %%p; print('✅ %%p')" 2>nul || (
        echo    ❌ %%p （インストールされていません）
        set "dependency_check_pass=false"
    )
)

if "%dependency_check_pass%"=="true" (
    echo ✅ PASS - 全ての依存関係が満たされています
    set /a passed_tests+=1
) else (
    echo ❌ FAIL - 一部の依存関係が不足しています
    echo    解決方法: maintenance_tool.bat → [2] 依存関係の更新
    set /a failed_tests+=1
)
echo.

:: テスト5: 設定ファイル
echo [TEST 5/6] ⚙️ 設定ファイルの妥当性
set /a total_tests+=1
set "config_check_pass=true"

if exist ".streamlit\config.toml" (
    findstr "port = 8502" .streamlit\config.toml >nul 2>&1
    if %errorLevel% == 0 (
        echo    ✅ ポート設定が正しいです (8502)
    ) else (
        echo    ❌ ポート設定が間違っています
        set "config_check_pass=false"
    )
    
    findstr "primaryColor" .streamlit\config.toml >nul 2>&1
    if %errorLevel% == 0 (
        echo    ✅ テーマ設定が存在します
    ) else (
        echo    ❌ テーマ設定が見つかりません
        set "config_check_pass=false"
    )
) else (
    echo    ❌ .streamlit\config.toml が見つかりません
    set "config_check_pass=false"
)

if "%config_check_pass%"=="true" (
    echo ✅ PASS - 設定ファイルは正常です
    set /a passed_tests+=1
) else (
    echo ❌ FAIL - 設定ファイルに問題があります
    echo    解決方法: maintenance_tool.bat → [5] 設定ファイルのリセット
    set /a failed_tests+=1
)
echo.

:: テスト6: UI起動テスト（オプション）
echo [TEST 6/6] 🚀 UI起動テスト（オプション）
echo    実際にUIを起動してテストしますか？ [Y/N]
echo    注意: このテストは数秒かかります
set /p ui_test=
set /a total_tests+=1

if /i "%ui_test%"=="Y" (
    echo    UI起動テストを実行中...
    echo    5秒後にStreamlitプロセスを終了します
    
    start /b python -m streamlit run frontend/app_modern.py --server.port 8502 --server.address 0.0.0.0 --server.headless true 2>nul
    
    timeout /t 3 /nobreak >nul
    
    netstat -ano | findstr :8502 >nul 2>&1
    if %errorLevel% == 0 (
        echo ✅ PASS - UIが正常に起動しました
        set /a passed_tests+=1
        
        :: プロセスを終了
        for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8502') do (
            taskkill /pid %%a /f >nul 2>&1
        )
        echo    テスト用UIプロセスを終了しました
    ) else (
        echo ❌ FAIL - UIの起動に失敗しました
        set /a failed_tests+=1
    )
) else (
    echo    UI起動テストをスキップしました
    set /a total_tests-=1
)
echo.

:: 結果サマリー
echo ████████████████████████████████████████████████████████████
echo ██                                                        ██
echo ██                   📊 テスト結果サマリー                  ██
echo ██                                                        ██
echo ████████████████████████████████████████████████████████████
echo.
echo 📈 テスト統計:
echo    • 総テスト数: %total_tests%
echo    • 成功: %passed_tests%
echo    • 失敗: %failed_tests%

set /a success_rate=(%passed_tests% * 100) / %total_tests%
echo    • 成功率: %success_rate%%%
echo.

if %failed_tests% == 0 (
    echo 🎉 全てのテストに合格しました！
    echo    システムは正常に動作する準備ができています。
    echo.
    echo 🚀 次のステップ:
    echo    1. quick_launch.bat でクイック起動
    echo    2. launch_chirp_ui.bat でフル機能起動
    echo    3. create_desktop_shortcut.bat でショートカット作成
) else (
    echo ⚠️  %failed_tests% 個のテストが失敗しました。
    echo    上記の解決方法を参考に修正してください。
    echo.
    echo 🔧 推奨アクション:
    echo    1. maintenance_tool.bat を実行
    echo    2. 失敗したテストの解決方法を実行
    echo    3. このテストを再実行
)

echo.
echo 💡 詳細なガイドは ONECLICK_LAUNCH_GUIDE.md を参照してください
echo.
pause
