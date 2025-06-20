@echo off
:: =================================================
:: 🧹 Chirp Trading System - アンインストール/クリーンアップ
:: =================================================
setlocal enabledelayedexpansion
color 0C

echo.
echo ████████████████████████████████████████████████████████████
echo ██                                                        ██
echo ██           🧹 システムクリーンアップツール               ██
echo ██                                                        ██
echo ████████████████████████████████████████████████████████████
echo.

echo ⚠️  警告: この操作により以下が削除されます:
echo.
echo 🗑️  削除対象:
echo    • Python仮想環境 (venv/)
echo    • Streamlitキャッシュ
echo    • ログファイル (logs/)
echo    • 一時ファイル・キャッシュ
echo    • デスクトップショートカット
echo    • ファイアウォールルール
echo.
echo 💾 保持されるもの:
echo    • ソースコード
echo    • 設定ファイル (.env, config/)
echo    • 取引データ (data/)
echo.

:MENU
echo 📋 クリーンアップメニュー:
echo.
echo [1] 🧹 軽量クリーンアップ（キャッシュのみ）
echo [2] 🔄 中程度クリーンアップ（仮想環境も含む）
echo [3] 💥 完全クリーンアップ（全て削除）
echo [4] 🗑️ デスクトップショートカット削除のみ
echo [5] 🔍 削除対象のプレビュー
echo [6] 🚪 終了
echo.
set /p choice="選択 (1-6): "

if "%choice%"=="1" goto LIGHT_CLEANUP
if "%choice%"=="2" goto MEDIUM_CLEANUP
if "%choice%"=="3" goto FULL_CLEANUP
if "%choice%"=="4" goto REMOVE_SHORTCUTS
if "%choice%"=="5" goto PREVIEW
if "%choice%"=="6" goto END
echo ❌ 無効な選択です
goto MENU

:LIGHT_CLEANUP
echo.
echo 🧹 軽量クリーンアップを実行中...
echo ================================

:: ポート8502のプロセス終了
echo 🌐 ポート8502のプロセスを確認中...
netstat -ano | findstr :8502 >nul 2>&1
if %errorLevel% == 0 (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8502') do (
        echo    プロセス %%a を終了中...
        taskkill /pid %%a /f >nul 2>&1
    )
)

:: Streamlitキャッシュ
echo 📦 Streamlitキャッシュをクリア中...
if exist "%USERPROFILE%\.streamlit\cache" (
    rmdir /s /q "%USERPROFILE%\.streamlit\cache" 2>nul
    echo    ✅ Streamlitキャッシュを削除
)

:: Pythonキャッシュ
echo 🐍 Pythonキャッシュをクリア中...
for /r . %%d in (__pycache__) do (
    if exist "%%d" (
        rmdir /s /q "%%d" 2>nul
        echo    ✅ %%d を削除
    )
)

:: 一時ファイル
echo 🗂️ 一時ファイルをクリア中...
del /q *.tmp 2>nul
del /q *.temp 2>nul
del /q *.pyc 2>nul

echo ✅ 軽量クリーンアップが完了しました
pause
goto MENU

:MEDIUM_CLEANUP
echo.
echo 🔄 中程度クリーンアップを実行中...
echo ===============================

echo 本当に仮想環境も削除しますか？ [Y/N]
echo （再インストールが必要になります）
set /p confirm_medium=
if /i not "%confirm_medium%"=="Y" goto MENU

:: 軽量クリーンアップの内容を実行
call :LIGHT_CLEANUP_SILENT

:: 仮想環境削除
echo 🐍 仮想環境を削除中...
if exist "venv" (
    rmdir /s /q "venv" 2>nul
    echo    ✅ 仮想環境を削除
)

:: ログファイル（一部）
echo 📊 古いログファイルを削除中...
if exist "logs" (
    forfiles /p logs /s /m *.log /d -7 /c "cmd /c del @path" 2>nul
    echo    ✅ 7日以上古いログファイルを削除
)

echo ✅ 中程度クリーンアップが完了しました
pause
goto MENU

:FULL_CLEANUP
echo.
echo 💥 完全クリーンアップを実行中...
echo ============================

echo ⚠️  この操作は取り消せません！
echo 本当に全てのキャッシュ・ログ・仮想環境を削除しますか？ [Y/N]
set /p confirm_full=
if /i not "%confirm_full%"=="Y" goto MENU

echo 最終確認: "DELETE" と入力してください
set /p final_confirm=
if not "%final_confirm%"=="DELETE" (
    echo キャンセルされました
    goto MENU
)

:: 中程度クリーンアップの内容を実行
call :MEDIUM_CLEANUP_SILENT

:: 全ログファイル
echo 📊 全ログファイルを削除中...
if exist "logs" (
    rmdir /s /q "logs" 2>nul
    echo    ✅ ログディレクトリを削除
)

:: データキャッシュ（バックテスト結果など）
echo 💾 データキャッシュを削除中...
if exist "data\cache" (
    rmdir /s /q "data\cache" 2>nul
    echo    ✅ データキャッシュを削除
)

:: デスクトップショートカット
call :REMOVE_SHORTCUTS_SILENT

:: ファイアウォールルール（管理者権限がある場合）
net session >nul 2>&1
if %errorLevel% == 0 (
    echo 🔒 ファイアウォールルールを削除中...
    netsh advfirewall firewall delete rule name="Streamlit Port 8502" >nul 2>&1
    echo    ✅ ファイアウォールルールを削除
)

echo ✅ 完全クリーンアップが完了しました
echo.
echo 💡 再インストール手順:
echo    1. launch_chirp_ui.bat を実行
echo    2. 自動セットアップに従う
echo    3. create_desktop_shortcut.bat でショートカット再作成
pause
goto MENU

:REMOVE_SHORTCUTS
echo.
echo 🗑️ デスクトップショートカットを削除中...
echo ====================================

call :REMOVE_SHORTCUTS_SILENT
echo ✅ ショートカット削除が完了しました
pause
goto MENU

:REMOVE_SHORTCUTS_SILENT
:: デスクトップパスを取得
for /f "tokens=2*" %%a in ('reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders" /v Desktop 2^>nul') do set "DESKTOP=%%b"
if not defined DESKTOP set "DESKTOP=%USERPROFILE%\Desktop"

:: ショートカットファイル
set "SHORTCUT_NAMES=🚀 Chirp Trading UI.lnk Chirp Trading UI.lnk"

for %%s in (%SHORTCUT_NAMES%) do (
    if exist "%DESKTOP%\%%s" (
        del "%DESKTOP%\%%s" 2>nul
        echo    ✅ %%s を削除
    )
)
goto :eof

:LIGHT_CLEANUP_SILENT
:: 軽量クリーンアップの処理（エコーなし）
netstat -ano | findstr :8502 >nul 2>&1
if %errorLevel% == 0 (
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8502') do (
        taskkill /pid %%a /f >nul 2>&1
    )
)
if exist "%USERPROFILE%\.streamlit\cache" rmdir /s /q "%USERPROFILE%\.streamlit\cache" 2>nul
for /r . %%d in (__pycache__) do if exist "%%d" rmdir /s /q "%%d" 2>nul
del /q *.tmp *.temp *.pyc 2>nul
goto :eof

:MEDIUM_CLEANUP_SILENT
call :LIGHT_CLEANUP_SILENT
if exist "venv" rmdir /s /q "venv" 2>nul
if exist "logs" forfiles /p logs /s /m *.log /d -7 /c "cmd /c del @path" 2>nul
goto :eof

:PREVIEW
echo.
echo 🔍 削除対象のプレビュー
echo ===================

echo 📊 現在のシステム状況:
echo.

:: ディスクサイズ
echo 💾 ディスク使用量:
if exist "venv" (
    for /f %%i in ('dir /s /a "venv" 2^>nul ^| find "バイト"') do echo    仮想環境: %%i
)
if exist "logs" (
    for /f %%i in ('dir /s /a "logs" 2^>nul ^| find "バイト"') do echo    ログファイル: %%i
)

:: ファイル数
echo.
echo 📁 ファイル数:
if exist "venv" (
    for /f %%i in ('dir /s /b "venv\*" 2^>nul ^| find /c /v ""') do echo    仮想環境: %%i ファイル
)
if exist "logs" (
    for /f %%i in ('dir "logs\*.log" 2^>nul ^| find /c " .log"') do echo    ログファイル: %%i 個
)

:: プロセス
echo.
echo 🌐 アクティブプロセス:
netstat -ano | findstr :8502 >nul 2>&1
if %errorLevel% == 0 (
    echo    ポート8502使用中のプロセス:
    netstat -ano | findstr :8502
) else (
    echo    ポート8502を使用中のプロセスなし
)

:: ショートカット
echo.
echo 🖱️ デスクトップショートカット:
for /f "tokens=2*" %%a in ('reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders" /v Desktop 2^>nul') do set "DESKTOP=%%b"
if not defined DESKTOP set "DESKTOP=%USERPROFILE%\Desktop"

if exist "%DESKTOP%\🚀 Chirp Trading UI.lnk" (
    echo    ✅ 🚀 Chirp Trading UI.lnk
) else (
    echo    ❌ ショートカットなし
)

pause
goto MENU

:END
echo.
echo 👋 クリーンアップツールを終了します
pause
exit /b 0
