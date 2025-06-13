"""
戦略テンプレート

新しい戦略を作成する際のテンプレート
このファイルをコピーして、独自の戦略を実装してください。
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple, Optional

from .base_strategy import BaseStrategy, Signal
from ..indicator import IndicatorCalculator


class TemplateStrategy(BaseStrategy):
    """
    戦略テンプレートクラス
    
    このクラスを継承して独自の戦略を実装します。
    """
    
    def __init__(self, strategy_id: str = 'template_strategy', params: Optional[Dict[str, Any]] = None):
        """
        初期化
        
        Args:
            strategy_id: 戦略ID
            params: 戦略パラメータ
        """
        # デフォルトパラメータを定義
        default_params = {
            'param1': 20,           # パラメータ1の説明
            'param2': 50,           # パラメータ2の説明
            'threshold': 0.02,      # 閾値
            'use_filter': True,     # フィルター使用フラグ
        }
        
        # 親クラスの初期化（デフォルトパラメータを渡す）
        super().__init__(strategy_id, {**default_params, **(params or {})})
        
        # 戦略固有の初期化
        self.indicator_calc = IndicatorCalculator()
        self._setup_strategy()
    
    def _setup_strategy(self):
        """戦略固有の初期化処理"""
        # 必要に応じて初期化処理を追加
        self.logger.info(f"戦略パラメータ: {self.params}")
    
    def generate_signal(self, df: pd.DataFrame, current_position: Dict[str, Any], 
                       account_info: Dict[str, Any]) -> Tuple[Signal, Dict[str, Any]]:
        """
        シグナルを生成する
        
        Args:
            df: 指標が計算されたOHLCVデータフレーム
            current_position: 現在のポジション情報
            account_info: 口座情報
        
        Returns:
            (シグナル, 詳細情報)のタプル
        """
        # データが不足している場合は何もしない
        if len(df) < max(self.params['param1'], self.params['param2']):
            return Signal.HOLD, {'reason': 'データ不足'}
        
        # 最新のデータを取得
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # シグナル詳細情報を初期化
        details = {
            'timestamp': latest.name if hasattr(latest, 'name') else str(df.index[-1]),
            'close': latest['close'],
            'indicators': {}
        }
        
        # ポジションチェック
        has_position = current_position is not None and current_position.get('side') is not None
        
        # エグジット条件をチェック（ポジションがある場合）
        if has_position:
            should_exit, exit_signal, exit_details = self.check_exit_conditions(df, current_position)
            if should_exit:
                details.update(exit_details)
                self.log_signal(exit_signal, details)
                return exit_signal, details
        
        # エントリー条件をチェック（ポジションがない場合）
        if not has_position:
            should_enter, entry_signal, entry_details = self.check_entry_conditions(df)
            if should_enter:
                details.update(entry_details)
                self.log_signal(entry_signal, details)
                return entry_signal, details
        
        return Signal.HOLD, details
    
    def check_entry_conditions(self, df: pd.DataFrame) -> Tuple[bool, Signal, Dict[str, Any]]:
        """
        エントリー条件をチェックする
        
        Args:
            df: データフレーム
        
        Returns:
            (条件を満たすか, シグナル, 詳細情報)のタプル
        """
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # ========================================
        # ここにエントリーロジックを実装
        # ========================================
        
        # 例: RSIが売られすぎゾーンから上昇
        if 'rsi' in df.columns:
            if prev['rsi'] < 30 and latest['rsi'] > 30:
                return True, Signal.BUY, {
                    'reason': 'RSI売られすぎからの回復',
                    'rsi_prev': prev['rsi'],
                    'rsi_current': latest['rsi']
                }
        
        # 例: 価格がボリンジャーバンド下限を下から上にクロス
        if 'bb_lower' in df.columns:
            if prev['close'] < prev['bb_lower'] and latest['close'] > latest['bb_lower']:
                return True, Signal.BUY, {
                    'reason': 'ボリンジャーバンド下限ブレイク',
                    'bb_lower': latest['bb_lower']
                }
        
        return False, Signal.HOLD, {}
    
    def check_exit_conditions(self, df: pd.DataFrame, current_position: Dict[str, Any]) -> Tuple[bool, Signal, Dict[str, Any]]:
        """
        エグジット条件をチェックする
        
        Args:
            df: データフレーム
            current_position: 現在のポジション情報
        
        Returns:
            (条件を満たすか, シグナル, 詳細情報)のタプル
        """
        latest = df.iloc[-1]
        position_side = current_position.get('side')
        entry_price = current_position.get('entry_price', 0)
        
        # ========================================
        # ここにエグジットロジックを実装
        # ========================================
        
        # 例: 利益確定（2%以上の利益）
        if position_side == 'LONG':
            profit_pct = (latest['close'] - entry_price) / entry_price
            if profit_pct > self.params['threshold']:
                return True, Signal.CLOSE_LONG, {
                    'reason': '利益確定',
                    'profit_pct': profit_pct * 100,
                    'entry_price': entry_price,
                    'exit_price': latest['close']
                }
        
        # 例: 損切り（-1%以下の損失）
        if position_side == 'LONG':
            loss_pct = (latest['close'] - entry_price) / entry_price
            if loss_pct < -self.params['threshold'] / 2:
                return True, Signal.CLOSE_LONG, {
                    'reason': '損切り',
                    'loss_pct': loss_pct * 100,
                    'entry_price': entry_price,
                    'exit_price': latest['close']
                }
        
        return False, Signal.HOLD, {}
    
    def calculate_confidence(self, df: pd.DataFrame, signal: Signal) -> float:
        """
        シグナルの確信度を計算する（0.0〜1.0）
        
        Args:
            df: データフレーム
            signal: シグナル
        
        Returns:
            確信度
        """
        # 複数の指標を組み合わせて確信度を計算
        confidence = 0.5  # ベース確信度
        
        latest = df.iloc[-1]
        
        # RSIによる確信度調整
        if 'rsi' in df.columns:
            if signal == Signal.BUY and latest['rsi'] < 40:
                confidence += 0.2
            elif signal == Signal.SELL and latest['rsi'] > 60:
                confidence += 0.2
        
        # ボリュームによる確信度調整
        if 'volume' in df.columns:
            avg_volume = df['volume'].rolling(20).mean().iloc[-1]
            if latest['volume'] > avg_volume * 1.5:
                confidence += 0.1
        
        # MACDによる確信度調整
        if 'macd' in df.columns and 'macd_signal' in df.columns:
            if signal == Signal.BUY and latest['macd'] > latest['macd_signal']:
                confidence += 0.1
            elif signal == Signal.SELL and latest['macd'] < latest['macd_signal']:
                confidence += 0.1
        
        return min(confidence, 1.0)
    
    def get_recommended_stop_loss(self, df: pd.DataFrame, signal: Signal) -> Optional[float]:
        """
        推奨ストップロス価格を取得する
        
        Args:
            df: データフレーム
            signal: シグナル
        
        Returns:
            ストップロス価格
        """
        latest = df.iloc[-1]
        
        # ATRベースのストップロス
        if 'atr' in df.columns:
            atr = latest['atr']
            if signal == Signal.BUY:
                # 買いの場合は現在価格からATR*2下
                return latest['close'] - (atr * 2)
            elif signal == Signal.SELL:
                # 売りの場合は現在価格からATR*2上
                return latest['close'] + (atr * 2)
        
        # ボリンジャーバンドベースのストップロス
        if 'bb_lower' in df.columns and 'bb_upper' in df.columns:
            if signal == Signal.BUY:
                return latest['bb_lower']
            elif signal == Signal.SELL:
                return latest['bb_upper']
        
        return None
    
    def get_recommended_take_profit(self, df: pd.DataFrame, signal: Signal) -> Optional[float]:
        """
        推奨テイクプロフィット価格を取得する
        
        Args:
            df: データフレーム
            signal: シグナル
        
        Returns:
            テイクプロフィット価格
        """
        latest = df.iloc[-1]
        stop_loss = self.get_recommended_stop_loss(df, signal)
        
        if stop_loss:
            # リスクリワード比2:1
            if signal == Signal.BUY:
                risk = latest['close'] - stop_loss
                return latest['close'] + (risk * 2)
            elif signal == Signal.SELL:
                risk = stop_loss - latest['close']
                return latest['close'] - (risk * 2)
        
        return None


# ========================================
# 戦略作成のガイドライン
# ========================================
"""
1. 戦略の命名規則:
   - ファイル名: xxx_strategy.py (例: momentum_strategy.py)
   - クラス名: XxxStrategy (例: MomentumStrategy)
   - strategy_id: xxx_strategy (例: momentum_strategy)

2. パラメータ設計:
   - デフォルト値は過去のバックテストで良好な結果を示した値に設定
   - パラメータ名は分かりやすく、単位を明記（例: ma_period_days）
   - 過剰な最適化を避ける（パラメータは5個以内を推奨）

3. シグナル生成:
   - 明確なエントリー/エグジット条件を定義
   - 複数の時間枠を使う場合は、上位足でトレンド確認
   - フィルター条件を追加して精度を向上

4. リスク管理:
   - 必ずストップロスを設定
   - ポジションサイズは口座残高の2%以内を推奨
   - 最大同時ポジション数を制限

5. デバッグとログ:
   - 重要な判断ポイントでログを出力
   - details辞書に判断根拠を詳細に記録
   - バックテスト結果を分析しやすくする

6. パフォーマンス:
   - 不要な計算を避ける（指標は事前計算済み）
   - DataFrameの操作は最小限に
   - ループ処理よりもベクトル演算を使用
"""
