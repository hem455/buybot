# 戦略開発ガイド

このドキュメントでは、新しい売買戦略を追加する方法を説明します。

## 📋 目次

1. [戦略の基本構造](#戦略の基本構造)
2. [新しい戦略の作成手順](#新しい戦略の作成手順)
3. [利用可能な指標](#利用可能な指標)
4. [サンプル戦略](#サンプル戦略)
5. [戦略のテスト方法](#戦略のテスト方法)
6. [ベストプラクティス](#ベストプラクティス)

## 戦略の基本構造

すべての戦略は `BaseStrategy` クラスを継承して実装します。

```python
import pandas as pd
from backend.strategy import BaseStrategy, Signal

class MyStrategy(BaseStrategy):
    def generate_signal(self, df, current_position, account_info):
        # シグナル生成ロジック
        return signal, details
```

## 新しい戦略の作成手順

### 1. テンプレートをコピー

```bash
# テンプレートをコピーして新しい戦略ファイルを作成
cp backend/strategy/template_strategy.py backend/strategy/my_new_strategy.py
```

### 2. 戦略を実装

```python
# backend/strategy/my_new_strategy.py

class MyNewStrategy(BaseStrategy):
    def __init__(self, strategy_id: str = 'my_new_strategy', params=None):
        default_params = {
            'fast_period': 10,
            'slow_period': 30,
            'rsi_threshold': 30
        }
        super().__init__(strategy_id, {**default_params, **(params or {})})
    
    def generate_signal(self, df, current_position, account_info):
        # 必要な指標の存在確認
        if 'rsi' not in df.columns:
            raise ValueError(f"Required indicator 'rsi' is missing from dataframe. Available columns: {list(df.columns)}")
        
        # データフレームが空でないかチェック
        if df.empty:
            raise ValueError("Dataframe is empty")
        
        # 最新データ
        latest = df.iloc[-1]
        
        # RSI値の有効性チェック
        if pd.isna(latest['rsi']):
            return Signal.HOLD, {'reason': 'RSI value is NaN, waiting for valid data'}
        
        # エントリー条件
        if not current_position:
            if latest['rsi'] < self.params['rsi_threshold']:
                return Signal.BUY, {'reason': 'RSI oversold', 'rsi': latest['rsi']}
        
        # エグジット条件
        elif current_position['side'] == 'LONG':
            if latest['rsi'] > 70:
                return Signal.CLOSE_LONG, {'reason': 'RSI overbought', 'rsi': latest['rsi']}
        
        return Signal.HOLD, {'rsi': latest['rsi']}
```

### 3. 戦略を登録

`backend/strategy/__init__.py` に追加:

```python
from .my_new_strategy import MyNewStrategy

# 戦略マネージャーに登録
strategy_manager.register_strategy('my_new_strategy', MyNewStrategy)
```

### 4. 設定ファイルに追加

`config/config.yaml` に追加:

```yaml
strategies:
  available:
    my_new_strategy:
      name: "私の新戦略"
      description: "RSIベースの逆張り戦略"
      parameters:
        fast_period: 10
        slow_period: 30
        rsi_threshold: 30
```

## 利用可能な指標

戦略で使用できる事前計算済みの指標：

### 移動平均
- `sma_7`, `sma_25`, `sma_99` - 単純移動平均
- `ema_12`, `ema_26` - 指数移動平均

### モメンタム指標
- `rsi` - RSI（相対力指数）
- `macd`, `macd_signal`, `macd_hist` - MACD
- `stoch_k`, `stoch_d` - ストキャスティクス

### ボラティリティ指標
- `bb_upper`, `bb_middle`, `bb_lower` - ボリンジャーバンド
- `atr` - Average True Range

### ボリューム指標
- `volume_sma` - ボリューム移動平均
- `obv` - On Balance Volume

### カスタム指標の追加

新しい指標が必要な場合は `backend/indicator/indicator_calculator.py` に追加:

```python
def calculate_custom_indicator(self, df: pd.DataFrame) -> pd.DataFrame:
    # カスタム指標の計算
    df['my_indicator'] = df['close'].rolling(window=20).mean()
    return df
```

## サンプル戦略

### 1. ボリンジャーバンド + RSI戦略

```python
class BollingerRSIStrategy(BaseStrategy):
    def generate_signal(self, df, current_position, account_info):
        # 必要な指標の存在確認
        required_columns = ['close', 'bb_upper', 'bb_lower', 'bb_middle', 'rsi']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Required indicators are missing: {missing_columns}. Available: {list(df.columns)}")
        
        # データフレームが空でないかチェック
        if df.empty:
            raise ValueError("Dataframe is empty")
        
        latest = df.iloc[-1]
        
        # 指標値の有効性チェック
        if any(pd.isna(latest[col]) for col in required_columns):
            invalid_cols = [col for col in required_columns if pd.isna(latest[col])]
            return Signal.HOLD, {'reason': f'Invalid indicator values: {invalid_cols}'}
        
        # ポジションなし
        if not current_position:
            # 買いシグナル: 価格がBB下限を下回り、RSI < 30
            if latest['close'] < latest['bb_lower'] and latest['rsi'] < 30:
                return Signal.BUY, {
                    'reason': 'BB下限ブレイク + RSI売られすぎ',
                    'bb_lower': latest['bb_lower'],
                    'rsi': latest['rsi']
                }
            
            # 売りシグナル: 価格がBB上限を上回り、RSI > 70
            if latest['close'] > latest['bb_upper'] and latest['rsi'] > 70:
                return Signal.SELL, {
                    'reason': 'BB上限ブレイク + RSI買われすぎ',
                    'bb_upper': latest['bb_upper'],
                    'rsi': latest['rsi']
                }
        
        # ポジションあり
        else:
            # ロングポジションのクローズ
            if current_position['side'] == 'LONG':
                if latest['close'] > latest['bb_middle'] or latest['rsi'] > 70:
                    return Signal.CLOSE_LONG, {'reason': 'BB中央線到達 or RSI高値'}
            
            # ショートポジションのクローズ
            elif current_position['side'] == 'SHORT':
                if latest['close'] < latest['bb_middle'] or latest['rsi'] < 30:
                    return Signal.CLOSE_SHORT, {'reason': 'BB中央線到達 or RSI安値'}
        
        return Signal.HOLD, {}
```

### 2. マルチタイムフレーム戦略

```python
class MultiTimeframeStrategy(BaseStrategy):
    def __init__(self, strategy_id='multi_tf', params=None):
        super().__init__(strategy_id, params)
        self.higher_tf_data = {}  # 上位足データを保存
    
    def generate_signal(self, df, current_position, account_info):
        # 必要な列の存在確認
        required_columns = ['open', 'high', 'low', 'close', 'volume', 'rsi']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Required columns are missing: {missing_columns}. Available: {list(df.columns)}")
        
        # データフレームが空でないかチェック
        if df.empty:
            raise ValueError("Dataframe is empty")
        
        # 1時間足での判断（メイン）
        latest_1h = df.iloc[-1]
        
        # RSI値の有効性チェック
        if pd.isna(latest_1h['rsi']):
            return Signal.HOLD, {'reason': 'RSI value is NaN'}
        
        # 4時間足のトレンド確認（仮想的に計算）
        try:
            df_4h = df.resample('4H').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            })
        except Exception as e:
            return Signal.HOLD, {'reason': f'Failed to resample data: {str(e)}'}
        
        if len(df_4h) < 50:
            return Signal.HOLD, {'reason': 'データ不足'}
        
        # 4時間足のトレンド
        sma_20_4h = df_4h['close'].rolling(20).mean().iloc[-1]
        sma_50_4h = df_4h['close'].rolling(50).mean().iloc[-1]
        
        # SMA値の有効性チェック
        if pd.isna(sma_20_4h) or pd.isna(sma_50_4h):
            return Signal.HOLD, {'reason': '4H SMA values are NaN'}
        
        trend_4h = 'UP' if sma_20_4h > sma_50_4h else 'DOWN'
        
        # エントリー条件
        if not current_position:
            # 上位足が上昇トレンド + 1時間足でプルバック
            if trend_4h == 'UP' and latest_1h['rsi'] < 40:
                return Signal.BUY, {
                    'reason': '4H上昇トレンド中の押し目買い',
                    'trend_4h': trend_4h,
                    'rsi_1h': latest_1h['rsi']
                }
        
        return Signal.HOLD, {'trend_4h': trend_4h, 'rsi_1h': latest_1h['rsi']}
```

## 戦略のテスト方法

### 1. ユニットテスト

```python
# tests/test_my_strategy.py
import pytest
import pandas as pd
from backend.strategy import MyNewStrategy

def test_buy_signal():
    strategy = MyNewStrategy()
    
    # テストデータを作成
    df = pd.DataFrame({
        'close': [100, 98, 95, 93, 91],
        'rsi': [40, 35, 30, 25, 20]
    })
    
    signal, details = strategy.generate_signal(df, None, {})
    assert signal == Signal.BUY
    assert 'RSI oversold' in details['reason']
```

### 2. バックテスト

```bash
# 特定の戦略でバックテスト実行
python run_backtest.py --strategy my_new_strategy --symbol BTC_JPY --days 90
```

### 3. ペーパートレード

本番前に仮想取引でテスト:

```python
# config/config.yaml
trading:
  paper_trade: true  # ペーパートレードモード
```

## ベストプラクティス

### 1. エラーハンドリング（重要）

戦略でのエラーハンドリングは必須です：

```python
def generate_signal(self, df, current_position, account_info):
    # 1. 必要な指標の存在確認
    required_columns = ['close', 'rsi', 'macd']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Required indicators missing: {missing_columns}")
    
    # 2. データフレームの検証
    if df.empty:
        raise ValueError("Empty dataframe provided")
    
    # 3. NaN値のチェック
    latest = df.iloc[-1]
    if pd.isna(latest['rsi']):
        return Signal.HOLD, {'reason': 'RSI is NaN, waiting for valid data'}
    
    # 4. 計算例外の処理
    try:
        signal_strength = latest['macd'] / latest['rsi']
    except ZeroDivisionError:
        return Signal.HOLD, {'reason': 'Division by zero in calculation'}
    except Exception as e:
        self.logger.error(f"Calculation error: {e}")
        return Signal.HOLD, {'reason': f'Calculation error: {str(e)}'}
    
    return signal, details
```

### 2. リスク管理を最優先

```python
def generate_signal(self, df, current_position, account_info):
    # 口座残高チェック
    if account_info['margin_level'] < 1.5:
        return Signal.CLOSE_ALL, {'reason': '証拠金維持率低下'}
    
    # 最大ポジション数チェック
    if self.get_open_position_count() >= 3:
        return Signal.HOLD, {'reason': '最大ポジション数到達'}
```

### 2. ログを適切に記録

```python
def generate_signal(self, df, current_position, account_info):
    signal, details = self._calculate_signal(df)
    
    # 重要な判断はログに記録
    if signal != Signal.HOLD:
        self.logger.info(f"シグナル生成: {signal.value}")
        self.logger.info(f"詳細: {details}")
    
    return signal, details
```

### 3. パラメータの過剰最適化を避ける

```python
# ❌ 悪い例：パラメータが多すぎる
default_params = {
    'ma1': 7, 'ma2': 14, 'ma3': 21, 'ma4': 28,
    'rsi_buy': 28.5, 'rsi_sell': 71.5,
    'bb_period': 20.5, 'bb_std': 2.1,
    # ... 20個以上のパラメータ
}

# ✅ 良い例：シンプルで堅牢
default_params = {
    'fast_ma': 20,
    'slow_ma': 50,
    'stop_loss_atr': 2.0
}
```

### 4. 市場環境の変化に対応

```python
def _detect_market_regime(self, df):
    """市場環境を判定"""
    atr = df['atr'].iloc[-1]
    atr_avg = df['atr'].rolling(20).mean().iloc[-1]
    
    if atr > atr_avg * 1.5:
        return 'HIGH_VOLATILITY'
    elif atr < atr_avg * 0.5:
        return 'LOW_VOLATILITY'
    else:
        return 'NORMAL'

def generate_signal(self, df, current_position, account_info):
    market_regime = self._detect_market_regime(df)
    
    # 市場環境に応じて戦略を調整
    if market_regime == 'HIGH_VOLATILITY':
        # ポジションサイズを縮小
        self.position_size_multiplier = 0.5
```

### 5. エラーハンドリング

```python
def generate_signal(self, df, current_position, account_info):
    try:
        # 必要なデータの存在確認
        required_columns = ['close', 'rsi', 'atr']
        for col in required_columns:
            if col not in df.columns:
                self.logger.error(f"必要な列がありません: {col}")
                return Signal.HOLD, {'error': f'Missing {col}'}
        
        # 戦略ロジック
        return self._calculate_signal(df, current_position)
        
    except Exception as e:
        self.logger.error(f"シグナル生成エラー: {e}")
        return Signal.HOLD, {'error': str(e)}
```

## 次のステップ

1. **テンプレートから始める**: `template_strategy.py` をベースに開発
2. **既存戦略を参考に**: `ma_cross_strategy.py` や `macd_rsi_strategy.py` を参照
3. **小さく始める**: シンプルな戦略から始めて、徐々に複雑化
4. **バックテストで検証**: 最低3ヶ月分のデータでテスト
5. **ペーパートレード**: 1週間以上の仮想取引で確認

## よくある質問

**Q: どのくらいの期間のデータでバックテストすべき？**
A: 最低3ヶ月、理想的には1年以上のデータでテストしてください。

**Q: パラメータの最適化はどうすれば？**
A: Grid SearchやBayesian Optimizationを使用できますが、過剰適合に注意。

**Q: 複数の戦略を組み合わせられる？**
A: はい、ポートフォリオ戦略として実装可能です。

**Q: リアルタイムデータでのテストは？**
A: WebSocket APIを使用してリアルタイムデータでテスト可能です。
