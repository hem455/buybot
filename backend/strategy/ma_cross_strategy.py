"""
単純移動平均クロス戦略

短期移動平均と長期移動平均のクロスでエントリー・エグジットを行う戦略。
"""

from typing import Dict, Any, Tuple, Optional
import pandas as pd

from .base_strategy import BaseStrategy, Signal


class SimpleMovingAverageCrossStrategy(BaseStrategy):
    """単純移動平均クロス戦略"""
    
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """初期化"""
        super().__init__('ma_cross', params)
        
        # パラメータを取得
        self.short_period = self.params.get('short_period', 7)
        self.long_period = self.params.get('long_period', 25)
        self.confirmation_bars = self.params.get('confirmation_bars', 1)
        
        # 内部状態
        self.cross_detected = False
        self.cross_direction = None
        self.cross_bar_count = 0
    
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
        # データが不足している場合
        if len(df) < self.long_period + self.confirmation_bars:
            return Signal.HOLD, {'reason': 'データ不足'}
        
        # 必要な移動平均が計算されているか確認
        short_ma_col = f'sma_{self.short_period}'
        long_ma_col = f'sma_{self.long_period}'
        
        if short_ma_col not in df.columns or long_ma_col not in df.columns:
            self.logger.error(f"必要な移動平均が計算されていません: {short_ma_col}, {long_ma_col}")
            return Signal.HOLD, {'reason': '指標未計算'}
        
        # 最新のデータを取得
        current_idx = len(df) - 1
        current_short_ma = df[short_ma_col].iloc[current_idx]
        current_long_ma = df[long_ma_col].iloc[current_idx]
        prev_short_ma = df[short_ma_col].iloc[current_idx - 1]
        prev_long_ma = df[long_ma_col].iloc[current_idx - 1]
        current_price = df['close'].iloc[current_idx]
        
        # ポジションがない場合はエントリーシグナルをチェック
        if not current_position or current_position.get('side') is None:
            return self._check_entry_signal(
                current_short_ma, current_long_ma, 
                prev_short_ma, prev_long_ma, 
                current_price
            )
        
        # ポジションがある場合はエグジットシグナルをチェック
        return self._check_exit_signal(
            current_short_ma, current_long_ma, 
            prev_short_ma, prev_long_ma,
            current_price, current_position
        )
    
    def _check_entry_signal(self, current_short: float, current_long: float,
                           prev_short: float, prev_long: float,
                           current_price: float) -> Tuple[Signal, Dict[str, Any]]:
        """エントリーシグナルをチェック"""
        # ゴールデンクロス（短期MAが長期MAを上抜け）
        if prev_short <= prev_long and current_short > current_long:
            if not self.cross_detected or self.cross_direction != 'golden':
                self.cross_detected = True
                self.cross_direction = 'golden'
                self.cross_bar_count = 1
            else:
                self.cross_bar_count += 1
            
            # 確認バー数を満たした場合
            if self.cross_bar_count >= self.confirmation_bars:
                signal = Signal.BUY
                details = {
                    'reason': 'ゴールデンクロス',
                    'short_ma': current_short,
                    'long_ma': current_long,
                    'price': current_price,
                    'confirmation_bars': self.cross_bar_count
                }
                self.log_signal(signal, details)
                self.cross_detected = False
                self.cross_bar_count = 0
                return signal, details
        
        # デッドクロス（短期MAが長期MAを下抜け）
        elif prev_short >= prev_long and current_short < current_long:
            if not self.cross_detected or self.cross_direction != 'dead':
                self.cross_detected = True
                self.cross_direction = 'dead'
                self.cross_bar_count = 1
            else:
                self.cross_bar_count += 1
            
            # 確認バー数を満たした場合
            if self.cross_bar_count >= self.confirmation_bars:
                signal = Signal.SELL
                details = {
                    'reason': 'デッドクロス',
                    'short_ma': current_short,
                    'long_ma': current_long,
                    'price': current_price,
                    'confirmation_bars': self.cross_bar_count
                }
                self.log_signal(signal, details)
                self.cross_detected = False
                self.cross_bar_count = 0
                return signal, details
        
        # クロスが継続していない場合はリセット
        else:
            if self.cross_detected:
                self.cross_detected = False
                self.cross_bar_count = 0
        
        return Signal.HOLD, {'reason': 'エントリー条件なし'}
    
    def _check_exit_signal(self, current_short: float, current_long: float,
                          prev_short: float, prev_long: float,
                          current_price: float, position: Dict[str, Any]) -> Tuple[Signal, Dict[str, Any]]:
        """エグジットシグナルをチェック"""
        position_side = position.get('side')
        
        # ロングポジションの場合
        if position_side == 'LONG':
            # デッドクロスで決済
            if prev_short >= prev_long and current_short < current_long:
                signal = Signal.CLOSE_LONG
                details = {
                    'reason': 'デッドクロスによる決済',
                    'short_ma': current_short,
                    'long_ma': current_long,
                    'price': current_price,
                    'entry_price': position.get('entry_price', 0),
                    'pnl': current_price - position.get('entry_price', current_price)
                }
                self.log_signal(signal, details)
                return signal, details
        
        # ショートポジションの場合
        elif position_side == 'SHORT':
            # ゴールデンクロスで決済
            if prev_short <= prev_long and current_short > current_long:
                signal = Signal.CLOSE_SHORT
                details = {
                    'reason': 'ゴールデンクロスによる決済',
                    'short_ma': current_short,
                    'long_ma': current_long,
                    'price': current_price,
                    'entry_price': position.get('entry_price', 0),
                    'pnl': position.get('entry_price', current_price) - current_price
                }
                self.log_signal(signal, details)
                return signal, details
        
        return Signal.HOLD, {'reason': 'エグジット条件なし'}
    
    def calculate_confidence(self, df: pd.DataFrame, signal: Signal) -> float:
        """
        シグナルの確信度を計算する
        
        クロスの角度や移動平均の乖離率から確信度を計算
        """
        if signal == Signal.HOLD:
            return 0.0
        
        # 移動平均の乖離率を計算
        current_idx = len(df) - 1
        short_ma = df[f'sma_{self.short_period}'].iloc[current_idx]
        long_ma = df[f'sma_{self.long_period}'].iloc[current_idx]
        
        divergence_rate = abs(short_ma - long_ma) / long_ma
        
        # 乖離率が大きいほど確信度を高く
        if divergence_rate > 0.05:  # 5%以上
            return 0.9
        elif divergence_rate > 0.03:  # 3%以上
            return 0.8
        elif divergence_rate > 0.01:  # 1%以上
            return 0.7
        else:
            return 0.6
