@echo off
REM GMOコイン自動売買システム - セットアップスクリプト (Windows)

echo GMOコイン自動売買システムのセットアップを開始します...

REM プロジェクトルートに移動
cd /d "%~dp0\.."

REM .envファイルの作成
if not exist .env (
    echo .envファイルを作成します...
    copy .env.example .env
    echo .envファイルを作成しました。APIキーを設定してください。
) else (
    echo .envファイルは既に存在します。
)

REM 必要なディレクトリの作成
echo 必要なディレクトリを作成します...
if not exist data\ohlcv mkdir data\ohlcv
if not exist logs\trades mkdir logs\trades
if not exist tests mkdir tests

REM Dockerイメージのビルド
echo Dockerイメージをビルドします...
docker-compose build

REM 設定ファイルの確認
if not exist config\config.yaml (
    echo エラー: config\config.yamlが見つかりません。
    exit /b 1
)

echo.
echo セットアップが完了しました！
echo.
echo 次のステップ:
echo 1. .envファイルを編集してGMOコインのAPIキーを設定してください
echo 2. 必要に応じてconfig\config.yamlを編集してください
echo 3. 以下のコマンドでシステムを起動できます:
echo    docker-compose up -d
echo.
echo UIにアクセス: http://localhost:8501

pause
