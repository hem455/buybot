# 🔧 メンテナンス・チートシート

未来の自分へ。これだけ覚えておけば大丈夫。

## 🚨 緊急時の対応

### システムが動かない時
```bash
# 1. 依存関係の再インストール（大体これで解決）
pip install -r requirements.txt

# 2. 設定ファイルの確認
cp config/example_minimal.yaml config/config.yaml
# → 編集して最小限の設定にする

# 3. APIキーの確認
cat .env  # APIキーが設定されているか確認
```

### データが古い時
```bash
# 最新データを取得
python scripts/download_data.py --days 7
```

## 📍 重要ファイルの場所

| 何を直したい | どこを見る |
|------------|----------|
| 取引ロジック | `backend/strategy/*.py` |
| APIエラー | `backend/data_fetcher/rest_api.py` |
| リスク設定 | `config/config.yaml` の `risk_management` |
| UI画面 | `frontend/app.py` |
| ログ確認 | `logs/system_*.log` |

## 🎯 よくある修正

### 取引量を変える
```yaml
# config/config.yaml
risk_management:
  position_sizing:
    risk_per_trade: 0.01  # 1%に変更
```

### 新しい通貨ペアを追加
```yaml
# config/config.yaml
trading:
  symbol: "ETH_JPY"  # イーサリアムに変更
```

### デバッグモードにする
```bash
# .env
DEBUG=True
LOG_LEVEL=DEBUG
```

## 🔄 定期メンテナンス

### 月1回
- ログファイルの整理: `rm logs/system_*.log.zip`
- 取引記録のバックアップ: `cp -r logs/trades/ backup/`

### 3ヶ月に1回
- 依存関係の更新確認（ただし慎重に）
- Dockerイメージの再ビルド: `docker-compose build --no-cache`

## 💡 開発再開時のコマンド

```bash
# 環境セットアップ（Windows）
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 環境セットアップ（Mac/Linux）
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# テスト実行
pytest tests/ -v

# UI起動
python main.py --mode ui
```

## 🐛 デバッグのヒント

1. **エラーが出たら**
   - まず `logs/system_*.log` の最新ファイルを確認
   - エラーメッセージで検索: `grep ERROR logs/system_*.log`

2. **取引が実行されない**
   - リスク制限を確認: `config.yaml` の `max_drawdown_percentage`
   - 最小注文サイズを確認: `min_order_size`

3. **データが取得できない**
   - GMOコインのAPIステータスを確認
   - レート制限に引っかかってないか確認

## 📝 Git操作

```bash
# 変更を保存（.envは除外される）
git add -A
git commit -m "設定を更新"

# 特定のファイルだけコミット
git add config/config.yaml
git commit -m "リスク設定を調整"
```

---
**Remember**: シンプルに保つ。動けばOK。完璧を求めない。
