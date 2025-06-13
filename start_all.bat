@echo off
echo ==========================================
echo GMOコイン自動売買システム - フル起動
echo ==========================================
echo.

REM 仮想環境をアクティブ化
call venv\Scripts\activate

echo UI + 自動売買ボットを起動しています...
echo.
echo ブラウザが自動で開かない場合は、以下のURLにアクセスしてください：
echo http://localhost:8501
echo.
echo 終了するには、このウィンドウでCtrl+Cを押してください。
echo.

REM UIとボットを両方起動
python main.py --mode both
