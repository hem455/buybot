# GMOコイン自動売買システム

ビットコイン(BTC/JPY)の自動売買を行うPython製システムです。テクニカル指標に基づく売買戦略、バックテスト機能、リアルタイム取引、Web UIを提供します。

## 機能

- **自動売買**: 設定した戦略に基づき24時間自動で取引を実行
- **バックテスト**: 過去データを使用して戦略の検証が可能
- **Web UI**: Streamlitを使用した直感的な操作画面
- **リスク管理**: ポジションサイジング、ストップロス、最大ドローダウン管理
- **複数戦略対応**: 移動平均クロス、MACD+RSI等の戦略を実装済み
- **ロギング**: 詳細なシステムログと取引履歴（税務対応）

## システム要件

- Python 3.12+
- Docker & Docker Compose（推奨）
- GMOコインのAPIキー

## インストール

### 1. リポジトリのクローン

```bash
git clone https://github.com/yourusername/gmo-trading-bot.git
cd gmo-trading-bot
```

### 2. 環境変数の設定

`.env.example`を`.env`にコピーして、APIキーを設定してください：

```bash
cp .env.example .env
```

`.env`ファイルを編集：
```
GMO_API_KEY=your_api_key_here
GMO_API_SECRET=your_api_secret_here
```

### 3. Dockerを使用する場合（推奨）

```bash
# イメージのビルドと起動
docker-compose up -d

# UIにアクセス
# http://localhost:8502
```

### 4. ローカル環境で実行する場合

```bash
# 仮想環境の作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係のインストール
pip install -r requirements.txt

# UIの起動
python main.py --mode ui

# ボットの起動
python main.py --mode bot

# 両方を起動
python main.py --mode both
```

## 🚀 使い方

### クラシックUI
```bash
# シンプルな旧UI
start_ui.bat
```

### 🆕 モダンUI（推奨）
```bash
# かっこいいダークテーマのUI
start_modern_ui.bat
```

ブラウザで http://localhost:8502 にアクセス（自動で開きます）

## 設定

主な設定は`config/config.yaml`で行います：

- **取引設定**: 通貨ペア、最小/最大注文サイズ
- **戦略設定**: 使用する戦略とパラメータ
- **リスク管理**: ポジションサイズ、ストップロス設定
- **ロギング**: ログレベル、保存期間

## ディレクトリ構成

```
C:\AI\自動売買\
├── backend/              # バックエンドモジュール
│   ├── config_manager/   # 設定管理
│   ├── data_fetcher/     # データ取得
│   ├── indicator/        # テクニカル指標
│   ├── strategy/         # 売買戦略
│   ├── risk_manager/     # リスク管理
│   ├── order_executor/   # 注文実行
│   ├── backtester/       # バックテスト
│   └── logger/           # ロギング
├── frontend/             # Streamlit UI
├── config/               # 設定ファイル
├── data/                 # データ保存
├── logs/                 # ログファイル
├── tests/                # テスト
├── docker/               # Docker関連
├── main.py               # エントリーポイント
├── requirements.txt      # Python依存関係
├── docker-compose.yml    # Docker Compose設定
└── README.md             # このファイル
```

## 📦 データ取得について

### GMOコインAPIのデータ取得制限

- **取得可能期間**: 最大約1年分（通貨ペアと時間足による）
- **1回のリクエスト**: 最大1日分のデータ
- **レート制限**: Public API 10リクエスト/秒

### 対応通貨ペア

主要通貨：
- BTC_JPY (ビットコイン)
- ETH_JPY (イーサリアム)
- XRP_JPY (リップル)
- LTC_JPY (ライトコイン)
- BCH_JPY (ビットコインキャッシュ)

その他24通貨ペアに対応

### データダウンロード方法

```bash
# 基本的な使い方（BTC 1時間足）
python download_data_fix.py

# 複数通貨・複数時間足
python download_data_multi.py --symbols BTC_JPY ETH_JPY --intervals 1hour 4hour 1day --days 180

# Windows用バッチファイル
download_data_all.bat
```

### バックテストに必要なデータ量

- **最低限**: 30日分（統計的信頼性が低い）
- **推奨**: 90日～180日分
- **理想**: 1年分以上（季節性や市場サイクルを含む）

## 🚀 戦略開発

### 現在利用可能な戦略

1. **単純移動平均クロス** (`simple_ma_cross`)
   - シンプルで安定した基本戦略

2. **MACD + RSI戦略** (`macd_rsi`)
   - モメンタムとオシレーターの組み合わせ

3. **ボリンジャーバンドブレイクアウト** (`bollinger_breakout`)
   - ボラティリティブレイクアウト戦略

4. **🆕 グリッドトレーディング** (`grid_trading`)
   - レンジ相場で効果的な自動売買
   - 複数の注文をグリッド状に配置

5. **🆕 マルチタイムフレーム** (`multi_timeframe`)
   - 複数の時間足を組み合わせた高精度戦略
   - 日足でトレンド、時間足でエントリー

6. **🆕 機械学習ベース** (`ml_based`)
   - ランダムフォレストを使用した予測モデル
   - 自動的に特徴量を学習・最適化

### 新しい戦略の追加

詳細は [STRATEGY_DEVELOPMENT.md](../_archive/STRATEGY_DEVELOPMENT.md) を参照してください。

```python
# 1. テンプレートをコピー
cp backend/strategy/template_strategy.py backend/strategy/my_strategy.py

# 2. 戦略を実装
# 3. config.yamlに追加
# 4. バックテストで検証
```

## トラブルシューティング

### よくある問題

1. **APIキーエラー**
   - `.env`ファイルにAPIキーが正しく設定されているか確認

2. **データが取得できない**
   - インターネット接続を確認
   - GMOコインのAPIステータスを確認

3. **バックテストデータがない**
   - 初回実行時はデータのダウンロードが必要
   - `data/ohlcv`ディレクトリを確認

## セキュリティ

- APIキーは必ず`.env`ファイルで管理し、コミットしない
- 本番環境では適切なファイアウォール設定を行う
- 定期的に依存関係を更新する

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## 免責事項

本システムは教育目的で作成されています。実際の取引での使用は自己責任で行ってください。投資には損失のリスクが伴います。

## サポート

問題や質問がある場合は、GitHubのIssueを作成してください。

## 貢献

プルリクエストは歓迎します。大きな変更の場合は、まずIssueを作成して変更内容を説明してください。
