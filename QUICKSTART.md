# GMOコイン自動売買システム - クイックスタートガイド

## はじめての方へ

このドキュメントでは、システムを初めて使う方向けに、最速で動かすための手順を説明します。

## 📋 前提条件

- Windows 10/11、macOS、またはLinux
- Python 3.12以上がインストール済み
- GMOコインのアカウントとAPIキー
- 基本的なコマンドライン操作の知識

## 🚀 5分でスタート

### ステップ1: システムのダウンロード

cd "C:\AI\自動売買"

git add .
git commit -m "変更内容の説明"
git push

```bash
# Gitがある場合
git clone https://github.com/yourusername/gmo-trading-bot.git
cd gmo-trading-bot

# または、ZIPファイルをダウンロードして解凍
```

### ステップ2: 環境設定

1. **環境変数ファイルを作成**
```bash
# Windows
copy .env.example .env

# Mac/Linux
cp .env.example .env
```

2. **.envファイルを編集**
```
GMO_API_KEY=あなたのAPIキー
GMO_API_SECRET=あなたのAPIシークレット
```

### ステップ3: 簡単起動（Windows）

1. **データをダウンロード**
   ```
   download_data.bat
   ```

2. **UIを起動**
   ```
   start_ui.bat
   ```

3. **ブラウザが自動で開きます** (http://localhost:8501)

### 🆕 更新方法

新しい機械学習ライブラリをインストール：
```
update_packages.bat
```

### ステップ3: 依存関係のインストール

```bash
# 仮想環境を作成（推奨）
python -m venv venv

# 仮想環境を有効化
# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

# パッケージをインストール
pip install -r requirements.txt
```

### ステップ3.5: 🆕 過去データのダウンロード

#### 方法A: 簡単バッチファイル（Windows）
```bash
# ビットコインの1時間足データ
download_data.bat

# または複数通貨（BTC/ETH）の複数時間足
download_data_all.bat
```

#### 方法B: コマンドライン
```bash
# 基本的な使い方（BTC 1時間足）
python download_data_fix.py

# イーサリアムも含めて複数通貨・複数時間足
python download_data_multi.py --symbols BTC_JPY ETH_JPY --intervals 1hour 4hour 1day

# 全主要通貨の日足データ（長期バックテスト用）
python download_data_multi.py --symbols BTC_JPY ETH_JPY XRP_JPY --intervals 1day --days 365
```

⚠️ **重要**: データがないとバックテストができません！必ず実行してください。

### ステップ4: システム起動

#### 方法A: venv環境で起動（開発向け）
```bash
# 仮想環境を有効化
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

# UIを起動
python main.py --mode ui

# またはボットとUIを両方起動
python main.py --mode both
```

#### 方法B: Dockerで起動（本番向け）
```bash
# 初回のみ：イメージをビルド
docker-compose build

# システム起動
docker-compose up -d

# ログ確認
docker-compose logs -f

# 停止
docker-compose down
```

ブラウザが自動で開かない場合は、http://localhost:8501 にアクセスしてください。

## 📊 最初のバックテスト

1. ブラウザでUIを開く
2. 「バックテスト」タブを選択
3. 以下を設定:
   - 戦略: 「単純移動平均クロス」
   - 期間: 過去30日
   - 初期資金: 1,000,000円
4. 「バックテスト実行」をクリック
5. 結果を確認

## 📖 重要指標の読み方

### バックテスト結果を正しく評価するために

| 指標 | 意味 | 良い値 | 危険な値 |
|------|------|---------|----------|
| **シャープレシオ** | リスク調整後リターン | 1.0以上 | 0.5未満 |
| **最大ドローダウン** | 資産の最大下落率 | 20%以下 | 30%以上 |
| **勝率** | 勝ちトレードの割合 | 40-70% | 80%以上（過剰適合？） |
| **Buy & Hold比較** | 単純保有との差 | プラス | マイナス |

### 🚨 特に注意すべき点

1. **「高リターン」に騙されるな！**
   - リターンが高くても、シャープレシオが低い = ギャンブル
   - ドローダウンが大きい = 精神的に耐えられない

2. **Buy & Holdに負ける = 意味なし**
   - 手数料やリスクを考えると、BTCを持つだけの方が優れていることが多い
   - 複雑な戦略が必ずしも良いわけではない

3. **勝率80%以上はファンタジー**
   - 過去データに完璧にフィットしすぎている可能性大
   - 実運用ではまったく機能しないかも

### データのダウンロード
```bash
# 過去30日分の1時間足データを取得
python scripts/download_data.py --symbol BTC_JPY --interval 1hour --days 30
```

### テストの実行
```bash
pytest tests/
```

### ログの確認
```bash
# システムログ
tail -f logs/system_*.log

# 取引ログ
cat logs/trades/trades_*.csv
```

## 📁 重要なファイルの場所

| ファイル/フォルダ | 説明 | 場所 |
|-----------------|------|------|
| 設定ファイル | システムの動作設定 | `config/config.yaml` |
| APIキー | GMOコインの認証情報 | `.env` |
| バックテストデータ | 過去の価格データ | `data/ohlcv/` |
| システムログ | エラーや動作記録 | `logs/system_*.log` |
| 取引記録 | 税務申告用の記録 | `logs/trades/` |
| 戦略コード | 売買ロジック | `backend/strategy/` |

## ⚙️ 基本的な設定変更

### 1. 取引通貨ペアの変更
`config/config.yaml`を編集:
```yaml
trading:
  symbol: "ETH_JPY"  # BTC_JPYから変更
```

### 2. リスク設定の変更
```yaml
risk_management:
  position_sizing:
    risk_per_trade: 0.01  # 1取引あたり総資産の1%
```

### 3. 戦略パラメータの変更
```yaml
strategies:
  available:
    simple_ma_cross:
      parameters:
        short_period: 10  # 短期移動平均を10に変更
        long_period: 30   # 長期移動平均を30に変更
```

## 🔍 トラブルシューティング

### よくあるエラーと対処法

#### "ModuleNotFoundError"
```bash
# 依存関係を再インストール
pip install -r requirements.txt
```

#### "API認証エラー"
1. `.env`ファイルのAPIキーを確認
2. GMOコインでAPIキーが有効か確認
3. APIキーに取引権限があるか確認

#### "データが見つかりません"
```bash
# データをダウンロード
python scripts/download_data.py
```

## 📚 次のステップ

1. **[ARCHITECTURE.md](ARCHITECTURE.md)** - システムの詳細な構造を理解
2. **[README.md](README.md)** - プロジェクト全体の説明
3. **戦略のカスタマイズ** - `backend/strategy/`のコードを参考に独自戦略を作成
4. **本番環境への移行** - Dockerを使用した安全な運用

## ⚠️ 注意事項

- **必ず少額でテスト**してから本格運用を開始してください
- **APIキーは絶対に公開**しないでください（GitHubにpushしない）
- **定期的にバックアップ**を取ってください（特に取引ログ）
- 投資は自己責任です。**損失のリスク**があります

## 💬 サポート

問題が解決しない場合:
1. `logs/`フォルダのエラーログを確認
2. [ARCHITECTURE.md](ARCHITECTURE.md)の詳細説明を参照
3. GitHubのIssueで質問

---
Happy Trading! 🚀
