# 🎨 モダンUI起動ガイド

## クイックスタート

### 1. デモデータを生成（初回のみ）

```bash
generate_demo_data.bat
```

### 2. モダンUIを起動

```bash
start_modern_ui.bat
```

### 3. ブラウザでアクセス

http://localhost:8501

## 📊 チャート機能

### メインのチャートタブ

**Chartsタブ**で以下の機能が利用可能：

1. **ローソク足チャート**
   - リアルタイム価格表示
   - ボリューム表示
   - テクニカル指標（RSI, MACD）
   - ボリンジャーバンド

2. **オーダーブック（板情報）**
   - 買い注文と売り注文の深度
   - リアルタイム更新

3. **価格分布**
   - 7日間の価格ヒストグラム
   - ボラティリティ分析

### チャートの操作

- **ズーム**: マウスホイール
- **パン**: ドラッグ
- **リセット**: ダブルクリック
- **データ表示**: ホバー

### シンボルと時間足

**対応シンボル:**
- BTC_JPY (ビットコイン)
- ETH_JPY (イーサリアム)
- XRP_JPY (リップル)
- LTC_JPY (ライトコイン)

**時間足:**
- 1分足
- 5分足
- 15分足
- 30分足
- 1時間足
- 4時間足
- 日足

## UIの特徴

### 🌑 ダークテーマ
- 目に優しいダークモード
- プロフェッショナルな配色
- 高コントラストで視認性向上

### 📊 リッチなビジュアル
- インタラクティブなチャート
- リアルタイムデータ表示
- アニメーション効果

### 🎯 主要機能

#### Dashboard（ダッシュボード）
- 総資産とP/L表示
- ポジション一覧
- 市場価格モニター
- ポートフォリオパフォーマンスチャート

#### Backtest（バックテスト）
- 戦略選択
- 期間設定
- パフォーマンス分析
- Buy & Hold比較

#### Strategies（戦略管理）
- アクティブな戦略の監視
- パフォーマンス統計
- 戦略の有効化/無効化

#### Analytics（詳細分析）
- 月次リターンヒートマップ
- リスクメトリクス
- パフォーマンス指標

## カスタマイズ

### カラーテーマの変更

`.streamlit/config.toml`を編集：

```toml
[theme]
primaryColor = "#ff6b35"  # メインカラー
backgroundColor = "#0e1117"  # 背景色
secondaryBackgroundColor = "#1a1d24"  # カード背景色
textColor = "#fafafa"  # テキスト色
```

### チャートカラーの変更

`frontend/components.py`で定義されているカラーパレットを編集：

```python
colors = {
    "success": "#00d4aa",  # 成功・プラス
    "danger": "#ff4757",   # 危険・マイナス
    "primary": "#ff6b35",  # プライマリ
    "info": "#45b7d1"      # 情報
}
```

## トラブルシューティング

### UIが起動しない場合

1. **ポートの確認**
   ```bash
   netstat -ano | findstr :8501
   ```
   他のアプリがポート8501を使用していないか確認

2. **パッケージの確認**
   ```bash
   pip install streamlit plotly pandas numpy
   ```

3. **ファイアウォール**
   - Windows Defenderでポート8501を許可

### データが表示されない場合

1. **データダウンロード**
   ```bash
   download_data_all.bat
   ```

2. **API接続確認**
   - `.env`ファイルのAPIキー確認
   - GMOコインAPIの状態確認

### パフォーマンスが悪い場合

1. **キャッシュクリア**
   ```bash
   streamlit cache clear
   ```

2. **ブラウザ変更**
   - Chrome推奨
   - ハードウェアアクセラレーション有効化

## 開発者向け情報

### 新しいコンポーネントの追加

`frontend/components.py`に新しいコンポーネントを追加：

```python
@staticmethod
def render_custom_card(title: str, value: Any) -> str:
    return f"""
    <div class="metric-card">
        <div class="metric-label">{title}</div>
        <div class="metric-value">{value}</div>
    </div>
    """
```

### カスタムCSSの追加

`frontend/app_modern.py`の`apply_custom_css()`関数に追加：

```css
.custom-class {
    background-color: #1a1d24;
    border-radius: 10px;
    padding: 1rem;
}
```

## 📸 スクリーンショット

### ダッシュボード
- リアルタイムポートフォリオ価値
- アクティブポジション
- 市場価格

### バックテスト結果
- 詳細なパフォーマンス指標
- 視覚的なチャート
- リスク分析

### 戦略管理
- 各戦略のステータス
- パフォーマンス比較
- 設定管理

## 🚀 今後の機能追加予定

1. **リアルタイムアップデート**
   - WebSocketによる価格更新
   - ライブチャート

2. **通知機能**
   - デスクトップ通知
   - 音声アラート

3. **カスタマイズ可能なダッシュボード**
   - ウィジェットの配置変更
   - テーマのカスタマイズ

4. **モバイル対応**
   - レスポンシブデザイン
   - タッチ操作対応
