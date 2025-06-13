# ベースイメージ
FROM python:3.12-slim

# 作業ディレクトリを設定
WORKDIR /app

# システムの依存関係をインストール
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    git \
    && rm -rf /var/lib/apt/lists/*

# Pythonの依存関係をコピー
COPY requirements.txt .

# Pythonパッケージをインストール
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# 必要なディレクトリを作成
RUN mkdir -p logs data/ohlcv

# 環境変数を設定
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# ポートを公開
EXPOSE 8501

# デフォルトコマンド（UIモード）
CMD ["python", "main.py", "--mode", "ui"]
