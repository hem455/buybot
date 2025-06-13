@echo off
echo ==========================================
echo GMOコイン自動売買システム - パッケージ更新
echo ==========================================
echo.

REM 仮想環境をアクティブ化
call venv\Scripts\activate

echo 機械学習ライブラリを含む新しいパッケージをインストールしています...
echo.

REM パッケージを更新
pip install -r requirements.txt --upgrade

echo.
echo パッケージの更新が完了しました！
echo.
echo 新しく追加された戦略:
echo - グリッドトレーディング戦略
echo - マルチタイムフレーム戦略
echo - 機械学習ベース戦略
echo.
pause
