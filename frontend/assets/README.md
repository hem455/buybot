# Chirp Trading System - Assets

## ロゴとアイコン

システムで使用するアイコンとアセットの管理

### カラーパレット

- **Primary Orange**: `#ff6b35`
- **Success Green**: `#00d4aa`
- **Danger Red**: `#ff4757`
- **Background Dark**: `#0e1117`
- **Card Background**: `#1a1d24`
- **Border Color**: `#2d3139`
- **Text Primary**: `#fafafa`
- **Text Secondary**: `#a3a3a3`

### アイコン（Emoji）

- 📊 ダッシュボード
- 🔄 バックテスト
- ⚙️ 戦略
- 📈 分析
- 💰 残高
- 📉 損失
- 🟢 稼働中
- 🔴 停止中
- ⚡ 高頻度
- 🎯 ターゲット
- 🛡️ リスク管理
- 🤖 AI/ML

### チャートテーマ

Plotlyダークテーマをベースに、カスタムカラーを適用：

```python
chart_theme = {
    "template": "plotly_dark",
    "paper_bgcolor": "rgba(26, 29, 36, 1)",
    "plot_bgcolor": "rgba(26, 29, 36, 1)",
    "font": {
        "color": "#fafafa"
    },
    "colorway": ["#ff6b35", "#00d4aa", "#4ecdc4", "#45b7d1", "#5d76cb", "#6c5ce7"]
}
```

### グラデーション

```css
/* Success Gradient */
background: linear-gradient(135deg, #00d4aa 0%, #00b894 100%);

/* Danger Gradient */
background: linear-gradient(135deg, #ff6b35 0%, #ff4757 100%);

/* Card Gradient */
background: linear-gradient(135deg, #1a1d24 0%, #2d3139 100%);
```
