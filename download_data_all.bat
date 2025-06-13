@echo off
echo ==========================================
echo GMOコイン自動売買システム - 複数通貨データダウンロード
echo ==========================================
echo.

REM 仮想環境をアクティブ化
call venv\Scripts\activate

echo 複数の暗号通貨データをダウンロードします...
echo.

REM ビットコインとイーサリアムの1時間足と日足をダウンロード
python download_data_multi.py --symbols BTC_JPY ETH_JPY --intervals 1hour 1day --days 180

echo.
echo =====================================
echo 追加のデータをダウンロードする場合:
echo =====================================
echo.
echo 例1: リップルを追加
echo python download_data_multi.py --symbols XRP_JPY --intervals 1hour
echo.
echo 例2: 全主要通貨の複数時間足
echo python download_data_multi.py --symbols BTC_JPY ETH_JPY XRP_JPY LTC_JPY BCH_JPY --intervals 15min 1hour 4hour 1day
echo.
echo 利用可能な通貨ペア:
echo BTC_JPY, ETH_JPY, BCH_JPY, LTC_JPY, XRP_JPY, XEM_JPY, XLM_JPY, BAT_JPY, OMG_JPY, XTZ_JPY, 
echo QTUM_JPY, ENJ_JPY, DOT_JPY, ATOM_JPY, XYM_JPY, MONA_JPY, ADA_JPY, MKR_JPY, DAI_JPY, LINK_JPY, 
echo FCR_JPY, DOGE_JPY, SOL_JPY, ASTR_JPY
echo.
pause
