@echo off
echo ==========================================
echo GMOコイン自動売買システム - データダウンロード
echo ==========================================
echo.

REM 仮想環境をアクティブ化
call venv\Scripts\activate

echo ビットコインの過去データ（1時間足）をダウンロードします...
echo.

REM データダウンロードを実行
python download_data_fix.py --symbol BTC_JPY --interval 1hour --days 90

echo.
echo データダウンロードが完了しました！
echo StreamlitのUIでバックテストを実行できます。
echo.
pause
