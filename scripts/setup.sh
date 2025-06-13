#!/bin/bash

# GMOコイン自動売買システム - セットアップスクリプト

echo "GMOコイン自動売買システムのセットアップを開始します..."

# プロジェクトルートに移動
cd "$(dirname "$0")/.."

# .envファイルの作成
if [ ! -f .env ]; then
    echo ".envファイルを作成します..."
    cp .env.example .env
    echo ".envファイルを作成しました。APIキーを設定してください。"
else
    echo ".envファイルは既に存在します。"
fi

# 必要なディレクトリの作成
echo "必要なディレクトリを作成します..."
mkdir -p data/ohlcv
mkdir -p logs/trades
mkdir -p tests

# Dockerイメージのビルド
echo "Dockerイメージをビルドします..."
docker-compose build

# 設定ファイルの確認
if [ ! -f config/config.yaml ]; then
    echo "エラー: config/config.yamlが見つかりません。"
    exit 1
fi

echo ""
echo "セットアップが完了しました！"
echo ""
echo "次のステップ:"
echo "1. .envファイルを編集してGMOコインのAPIキーを設定してください"
echo "2. 必要に応じてconfig/config.yamlを編集してください"
echo "3. 以下のコマンドでシステムを起動できます:"
echo "   docker-compose up -d"
echo ""
echo "UIにアクセス: http://localhost:8501"
