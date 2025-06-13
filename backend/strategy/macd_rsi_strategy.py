"""
MACD + RSI戦略

MACDシグナルとRSIを組み合わせた戦略。
RSIでトレンドの過熱感を判断し、MACDでエントリータイミングを計る。
"""

from typing import Dict, Any, Optional, Tuple
import pandas as pd

from .base_strategy import BaseStrategy, Signal


class MACDRSIStrategy(BaseStrategy):
    """MACD + RSI戦略"""
    
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        """初期化"""
        super().__init__('macd_rsi', params)
        
        # パラメータを取得
        self.rsi_oversold = self.params.get('rsi_oversold', 30)
        self.rsi_overbought = self.params.get('rsi_overbought', 70)
        self.macd_threshold = self.params.get('macd_threshold', 0)
    
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
        if len(df) < 50:  # MACD計算に必要な最小データ数
            return Signal.HOLD, {'reason': 'データ不足'}
        
        # 必要な指標が計算されているか確認
        required_columns = ['macd', 'macd_signal', 'macd_histogram', 'rsi']
        if not all(col in df.columns for col in required_columns):
            self.logger.error(f"必要な指標が計算されていません: {required_columns}")
            return Signal.HOLD, {'reason': '指標未計算'}
        
        # 最新のデータを取得
        current_idx = len(df) - 1
        current_macd = df['macd'].iloc[current_idx]
        current_signal = df['macd_signal'].iloc[current_idx]
        current_histogram = df['macd_histogram'].iloc[current_idx]
        prev_histogram = df['macd_histogram'].iloc[current_idx - 1]
        current_rsi = df['rsi'].iloc[current_idx]
        current_price = df['close'].iloc[current_idx]
        
        # NaNチェック
        if pd.isna(current_macd) or pd.isna(current_signal) or pd.isna(current_rsi):
            return Signal.HOLD, {'reason': '指標値がNaN'}
        
        # ポジションがない場合はエントリーシグナルをチェック
        if not current_position or current_position.get('side') is None:
            return self._check_entry_signal(
                current_macd, current_signal, current_histogram,
                prev_histogram, current_rsi, current_price
            )
        
        # ポジションがある場合はエグジットシグナルをチェック
        return self._check_exit_signal(
            current_macd, current_signal, current_histogram,
            prev_histogram, current_rsi, current_price, current_position
        )
    
    def _check_entry_signal(self, macd: float, signal: float, histogram: float,
                           prev_histogram: float, rsi: float, price: float) -> Tuple[Signal, Dict[str, Any]]:
        """エントリーシグナルをチェック"""
        # 買いシグナル
        # 条件: RSIが売られすぎ圏から回復 + MACDヒストグラムが正に転換
        if (rsi < self.rsi_oversold + 10 and  # RSIが売られすぎ圏付近
            prev_histogram <= 0 and histogram > 0 and  # ヒストグラムが正に転換
            macd > self.macd_threshold):  # MACDが閾値以上
            
            signal = Signal.BUY
            details = {
                'reason': 'RSI売られすぎ + MACDヒストグラム正転',
                'macd': macd,
                'macd_signal': signal,
                'macd_histogram': histogram,
                'rsi': rsi,
                'price': price
            }
            self.log_signal(signal, details)
            return signal, details
        
        # 売りシグナル
        # 条件: RSIが買われすぎ圏から下落 + MACDヒストグラムが負に転換
        if (rsi > self.rsi_overbought - 10 and  # RSIが買われすぎ圏付近
            prev_histogram >= 0 and histogram < 0 and  # ヒストグラムが負に転換
            macd < -self.macd_threshold):  # MACDが閾値以下
            
            signal = Signal.SELL
            details = {
                'reason': 'RSI買われすぎ + MACDヒストグラム負転',
                'macd': macd,
                'macd_signal': signal,
                'macd_histogram': histogram,
                'rsi': rsi,
                'price': price
            }
            self.log_signal(signal, details)
            return signal, details
        
        return Signal.HOLD, {'reason': 'エントリー条件なし'}
    
    def _check_exit_signal(self, macd: float, signal: float, histogram: float,
                          prev_histogram: float, rsi: float, price: float,
                          position: Dict[str, Any]) -> Tuple[Signal, Dict[str, Any]]:
        """エグジットシグナルをチェック"""
        position_side = position.get('side')
        entry_price = position.get('entry_price', price)
        
        # ロングポジションの場合
        if position_side == 'LONG':
            # 利確条件: RSIが買われすぎ圏に到達
            if rsi >= self.rsi_overbought:
                signal = Signal.CLOSE_LONG
                details = {
                    'reason': 'RSI買われすぎによる利確',
                    'rsi': rsi,
                    'price': price,
                    'entry_price': entry_price,
                    'pnl': price - entry_price
                }
                self.log_signal(signal, details)
                return signal, details
            
            # 損切り条件: MACDヒストグラムが大きく負に転換
            if histogram < -abs(self.macd_threshold) * 2:
                signal = Signal.CLOSE_LONG
                details = {
                    'reason': 'MACDヒストグラム悪化による損切り',
                    'macd_histogram': histogram,
                    'price': price,
                    'entry_price': entry_price,
                    'pnl': price - entry_price
                }
                self.log_signal(signal, details)
                return signal, details
        
        # ショートポジションの場合
        elif position_side == 'SHORT':
            # 利確条件: RSIが売られすぎ圏に到達
            if rsi <= self.rsi_oversold:
                signal = Signal.CLOSE_SHORT
                details = {
                    'reason': 'RSI売られすぎによる利確',
                    'rsi': rsi,
                    'price': price,
                    'entry_price': entry_price,
                    'pnl': entry_price - price
                }
                self.log_signal(signal, details)
                return signal, details
            
            # 損切り条件: MACDヒストグラムが大きく正に転換
            if histogram > abs(self.macd_threshold) * 2:
                signal = Signal.CLOSE_SHORT
                details = {
                    'reason': 'MACDヒストグラム悪化による損切り',
                    'macd_histogram': histogram,
                    'price': price,
                    'entry_price': entry_price,
                    'pnl': entry_price - price
                }
                self.log_signal(signal, details)
                return signal, details
        
        return Signal.HOLD, {'reason': 'エグジット条件なし'}
    
    def calculate_confidence(self, df: pd.DataFrame, signal: Signal) -> float:
        """
        シグナルの確信度を計算する
        
        RSIの極値からの距離とMACDの強さから確信度を計算
        """
        if signal == Signal.HOLD:
            return 0.0
        
        current_idx = len(df) - 1
        rsi = df['rsi'].iloc[current_idx]
        macd_histogram = df['macd_histogram'].iloc[current_idx]
        
        confidence = 0.5  # ベース確信度
        
        # RSIによる調整
        if signal in [Signal.BUY, Signal.CLOSE_SHORT]:
            if rsi < self.rsi_oversold:
                confidence += 0.2
            elif rsi < self.rsi_oversold + 10:
                confidence += 0.1
        elif signal in [Signal.SELL, Signal.CLOSE_LONG]:
            if rsi > self.rsi_overbought:
                confidence += 0.2
            elif rsi > self.rsi_overbought - 10:
                confidence += 0.1
        
        # MACDヒストグラムによる調整
        histogram_strength = abs(macd_histogram)
        if histogram_strength > 100:  # 強いシグナル
            confidence += 0.2
        elif histogram_strength > 50:  # 中程度のシグナル
            confidence += 0.1
        
        return min(confidence, 0.95)  # 最大95%
