"""
マルチタイムフレーム戦略

複数の時間足を組み合わせて、より精度の高いエントリーポイントを見つける戦略。
上位足でトレンド確認、下位足でエントリータイミングを計る。
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple, Optional, List

from .base_strategy import BaseStrategy, Signal
from ..indicator import IndicatorCalculator


class MultiTimeframeStrategy(BaseStrategy):
    """
    マルチタイムフレーム戦略
    
    複数の時間足を分析して売買判断を行う。
    例：日足でトレンド確認、4時間足で方向性確認、1時間足でエントリー
    """
    
    def __init__(self, strategy_id: str = 'multi_timeframe', params: Optional[Dict[str, Any]] = None):
        """
        初期化
        
        Args:
            strategy_id: 戦略ID
            params: 戦略パラメータ
        """
        # デフォルトパラメータ
        default_params = {
            # 時間足の設定（分単位）
            'tf_primary': 60,       # プライマリ（エントリー用）: 1時間
            'tf_secondary': 240,    # セカンダリ（方向確認用）: 4時間
            'tf_tertiary': 1440,    # ターシャリ（トレンド確認用）: 1日
            
            # 移動平均の期間
            'ma_fast': 20,
            'ma_slow': 50,
            'ma_trend': 200,
            
            # エントリー条件
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            'volume_threshold': 1.5,  # 平均ボリュームの倍率
            
            # フィルター
            'use_trend_filter': True,
            'use_momentum_filter': True,
            'min_trend_strength': 0.3,  # トレンド強度の最小値
        }
        
        super().__init__(strategy_id, {**default_params, **(params or {})})
        
        self.indicator_calc = IndicatorCalculator()
        self.timeframe_data = {}  # 各時間足のデータを保存
        
    def _resample_ohlcv(self, df: pd.DataFrame, target_minutes: int) -> pd.DataFrame:
        """
        OHLCVデータを指定の時間足にリサンプル
        
        Args:
            df: 元のデータフレーム（1分足想定）
            target_minutes: ターゲットの時間足（分）
        
        Returns:
            リサンプルされたデータフレーム
        """
        # タイムスタンプをインデックスに設定
        df_copy = df.copy()
        if 'timestamp' in df_copy.columns:
            df_copy.set_index('timestamp', inplace=True)
        
        # リサンプルルール
        rule = f'{target_minutes}T'  # T = minutes
        
        # OHLCVデータのリサンプル
        resampled = df_copy.resample(rule).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        # 指標を再計算
        resampled = self.indicator_calc.calculate_all(resampled)
        
        return resampled
    
    def _analyze_trend(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        トレンドを分析
        
        Args:
            df: データフレーム
        
        Returns:
            トレンド情報
        """
        if len(df) < self.params['ma_trend']:
            return {'trend': 'UNKNOWN', 'strength': 0}
        
        latest = df.iloc[-1]
        
        # 移動平均によるトレンド判定
        ma_fast = df['close'].rolling(self.params['ma_fast']).mean().iloc[-1]
        ma_slow = df['close'].rolling(self.params['ma_slow']).mean().iloc[-1]
        ma_trend = df['close'].rolling(self.params['ma_trend']).mean().iloc[-1]
        
        # トレンドの方向
        if ma_fast > ma_slow > ma_trend and latest['close'] > ma_trend:
            trend = 'STRONG_UP'
            strength = min((latest['close'] - ma_trend) / ma_trend, 1.0)
        elif ma_fast > ma_slow and latest['close'] > ma_slow:
            trend = 'UP'
            strength = min((latest['close'] - ma_slow) / ma_slow, 0.7)
        elif ma_fast < ma_slow < ma_trend and latest['close'] < ma_trend:
            trend = 'STRONG_DOWN'
            strength = min((ma_trend - latest['close']) / ma_trend, 1.0)
        elif ma_fast < ma_slow and latest['close'] < ma_slow:
            trend = 'DOWN'
            strength = min((ma_slow - latest['close']) / ma_slow, 0.7)
        else:
            trend = 'RANGE'
            strength = 0.3
        
        # ADXによるトレンド強度（もしあれば）
        if 'adx' in df.columns:
            adx = latest['adx']
            if adx > 40:
                strength = min(strength * 1.5, 1.0)
            elif adx < 20:
                strength = strength * 0.5
        
        return {
            'trend': trend,
            'strength': strength,
            'ma_fast': ma_fast,
            'ma_slow': ma_slow,
            'ma_trend': ma_trend
        }
    
    def _check_momentum(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        モメンタムをチェック
        
        Args:
            df: データフレーム
        
        Returns:
            モメンタム情報
        """
        latest = df.iloc[-1]
        
        momentum_data = {
            'rsi': latest.get('rsi', 50),
            'macd': latest.get('macd', 0),
            'macd_signal': latest.get('macd_signal', 0),
            'volume_ratio': 1.0
        }
        
        # ボリューム比率
        if 'volume' in df.columns and len(df) > 20:
            avg_volume = df['volume'].rolling(20).mean().iloc[-1]
            if avg_volume > 0:
                momentum_data['volume_ratio'] = latest['volume'] / avg_volume
        
        # モメンタムスコア計算
        score = 0
        
        # RSI
        if momentum_data['rsi'] < self.params['rsi_oversold']:
            score -= 1  # 売られすぎ
        elif momentum_data['rsi'] > self.params['rsi_overbought']:
            score += 1  # 買われすぎ
        
        # MACD
        if momentum_data['macd'] > momentum_data['macd_signal']:
            score += 0.5
        else:
            score -= 0.5
        
        # ボリューム
        if momentum_data['volume_ratio'] > self.params['volume_threshold']:
            score = score * 1.2  # 高ボリュームで強調
        
        momentum_data['score'] = score
        
        return momentum_data
    
    def generate_signal(self, df: pd.DataFrame, current_position: Dict[str, Any], 
                       account_info: Dict[str, Any]) -> Tuple[Signal, Dict[str, Any]]:
        """
        シグナルを生成する
        
        Args:
            df: OHLCVデータフレーム（最小時間足）
            current_position: 現在のポジション情報
            account_info: 口座情報
        
        Returns:
            (シグナル, 詳細情報)のタプル
        """
        # データが不足している場合
        min_length = max(self.params['ma_trend'], 200)
        if len(df) < min_length:
            return Signal.HOLD, {'reason': 'データ不足'}
        
        # 現在の時間足（プライマリ）の分析
        primary_analysis = {
            'trend': self._analyze_trend(df),
            'momentum': self._check_momentum(df)
        }
        
        # 上位時間足の分析（簡易的にリサンプル）
        # 実際の実装では、各時間足のデータを別々に取得する方が正確
        
        # セカンダリ時間足（4時間足想定）
        if len(df) > self.params['tf_secondary']:
            df_secondary = self._resample_ohlcv(df, self.params['tf_secondary'])
            secondary_trend = self._analyze_trend(df_secondary)
        else:
            secondary_trend = {'trend': 'UNKNOWN', 'strength': 0}
        
        # ターシャリ時間足（日足想定）
        if len(df) > self.params['tf_tertiary']:
            df_tertiary = self._resample_ohlcv(df, self.params['tf_tertiary'])
            tertiary_trend = self._analyze_trend(df_tertiary)
        else:
            tertiary_trend = {'trend': 'UNKNOWN', 'strength': 0}
        
        # 最新データ
        latest = df.iloc[-1]
        
        # シグナル詳細
        details = {
            'timestamp': latest.name if hasattr(latest, 'name') else str(df.index[-1]),
            'close': latest['close'],
            'primary_trend': primary_analysis['trend']['trend'],
            'secondary_trend': secondary_trend['trend'],
            'tertiary_trend': tertiary_trend['trend'],
            'momentum_score': primary_analysis['momentum']['score'],
            'rsi': primary_analysis['momentum']['rsi']
        }
        
        # ポジションがある場合はエグジット条件をチェック
        if current_position and current_position.get('side'):
            exit_signal = self._check_exit_conditions(
                current_position, 
                primary_analysis, 
                secondary_trend
            )
            if exit_signal != Signal.HOLD:
                details['reason'] = 'エグジット条件成立'
                return exit_signal, details
        
        # ポジションがない場合はエントリー条件をチェック
        if not current_position or not current_position.get('side'):
            entry_signal = self._check_entry_conditions(
                primary_analysis,
                secondary_trend,
                tertiary_trend
            )
            if entry_signal != Signal.HOLD:
                details['reason'] = 'エントリー条件成立'
                return entry_signal, details
        
        return Signal.HOLD, details
    
    def _check_entry_conditions(self, primary: Dict, secondary: Dict, tertiary: Dict) -> Signal:
        """
        エントリー条件をチェック
        
        Args:
            primary: プライマリ時間足の分析
            secondary: セカンダリ時間足の分析
            tertiary: ターシャリ時間足の分析
        
        Returns:
            シグナル
        """
        # トレンドフィルター
        if self.params['use_trend_filter']:
            # 上位足が同じ方向を向いていない場合はエントリーしない
            if tertiary['trend'] in ['STRONG_UP', 'UP'] and secondary['trend'] not in ['STRONG_UP', 'UP', 'UNKNOWN']:
                return Signal.HOLD
            if tertiary['trend'] in ['STRONG_DOWN', 'DOWN'] and secondary['trend'] not in ['STRONG_DOWN', 'DOWN', 'UNKNOWN']:
                return Signal.HOLD
        
        # 買いエントリー条件
        buy_conditions = [
            # 上位足が上昇トレンド
            tertiary['trend'] in ['STRONG_UP', 'UP', 'UNKNOWN'],
            secondary['trend'] in ['STRONG_UP', 'UP', 'RANGE'],
            # プライマリで押し目
            primary['momentum']['rsi'] < 40,
            # トレンド強度
            secondary.get('strength', 0) >= self.params['min_trend_strength']
        ]
        
        if all(buy_conditions):
            return Signal.BUY
        
        # 売りエントリー条件
        sell_conditions = [
            # 上位足が下降トレンド
            tertiary['trend'] in ['STRONG_DOWN', 'DOWN', 'UNKNOWN'],
            secondary['trend'] in ['STRONG_DOWN', 'DOWN', 'RANGE'],
            # プライマリで戻り
            primary['momentum']['rsi'] > 60,
            # トレンド強度
            secondary.get('strength', 0) >= self.params['min_trend_strength']
        ]
        
        if all(sell_conditions):
            return Signal.SELL
        
        return Signal.HOLD
    
    def _check_exit_conditions(self, position: Dict, primary: Dict, secondary: Dict) -> Signal:
        """
        エグジット条件をチェック
        
        Args:
            position: 現在のポジション
            primary: プライマリ時間足の分析
            secondary: セカンダリ時間足の分析
        
        Returns:
            シグナル
        """
        position_side = position.get('side')
        
        # ロングポジションのエグジット
        if position_side == 'LONG':
            exit_conditions = [
                # トレンド転換
                primary['trend']['trend'] in ['DOWN', 'STRONG_DOWN'],
                # RSI高値
                primary['momentum']['rsi'] > 80,
                # 上位足のトレンド転換
                secondary['trend'] in ['DOWN', 'STRONG_DOWN']
            ]
            
            if any(exit_conditions):
                return Signal.CLOSE_LONG
        
        # ショートポジションのエグジット
        elif position_side == 'SHORT':
            exit_conditions = [
                # トレンド転換
                primary['trend']['trend'] in ['UP', 'STRONG_UP'],
                # RSI安値
                primary['momentum']['rsi'] < 20,
                # 上位足のトレンド転換
                secondary['trend'] in ['UP', 'STRONG_UP']
            ]
            
            if any(exit_conditions):
                return Signal.CLOSE_SHORT
        
        return Signal.HOLD
    
    def calculate_confidence(self, df: pd.DataFrame, signal: Signal) -> float:
        """
        シグナルの確信度を計算
        
        Args:
            df: データフレーム
            signal: シグナル
        
        Returns:
            確信度（0.0〜1.0）
        """
        # 基本確信度
        confidence = 0.5
        
        # 複数時間足の整合性で確信度を上げる
        # （実際の実装では詳細な分析結果を使用）
        if signal in [Signal.BUY, Signal.SELL]:
            confidence += 0.3
        
        # ボリュームが高い場合
        if len(df) > 20:
            latest_volume = df['volume'].iloc[-1]
            avg_volume = df['volume'].rolling(20).mean().iloc[-1]
            if latest_volume > avg_volume * 1.5:
                confidence += 0.1
        
        return min(confidence, 0.9)
