"""
テクニカル指標計算モジュール

各種テクニカル指標を計算するモジュール。
pandas_taを使用して効率的に計算を行う。
"""

import pandas as pd
import pandas_ta as ta
from typing import Dict, Any, Optional, Union, List
import numpy as np

from ..config_manager import get_config_manager
from ..logger import get_logger


class IndicatorCalculator:
    """テクニカル指標計算クラス"""
    
    def __init__(self):
        """初期化"""
        self.config = get_config_manager()
        self.logger = get_logger()
        self.indicator_config = self.config.get('indicators', {})
    
    def calculate_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        設定されたすべての指標を計算する
        
        Args:
            df: OHLCVデータフレーム
        
        Returns:
            指標が追加されたデータフレーム
        """
        if df.empty:
            return df
        
        # データフレームのコピーを作成
        result_df = df.copy()
        
        # 各指標を計算
        if 'sma' in self.indicator_config:
            result_df = self.add_sma(result_df)
        
        if 'ema' in self.indicator_config:
            result_df = self.add_ema(result_df)
        
        if 'macd' in self.indicator_config:
            result_df = self.add_macd(result_df)
        
        if 'rsi' in self.indicator_config:
            result_df = self.add_rsi(result_df)
        
        if 'bollinger_bands' in self.indicator_config:
            result_df = self.add_bollinger_bands(result_df)
        
        if 'atr' in self.indicator_config:
            result_df = self.add_atr(result_df)
        
        return result_df
    
    def add_sma(self, df: pd.DataFrame, periods: Optional[List[int]] = None) -> pd.DataFrame:
        """
        単純移動平均（SMA）を計算して追加する
        
        Args:
            df: OHLCVデータフレーム
            periods: 期間のリスト（省略時は設定から取得）
        
        Returns:
            SMAが追加されたデータフレーム
        """
        if periods is None:
            periods = self.indicator_config.get('sma', {}).get('periods', [7, 25, 99])
        
        for period in periods:
            column_name = f'sma_{period}'
            try:
                # 既に計算済みの場合はスキップ
                if column_name not in df.columns:
                    df[column_name] = ta.sma(df['close'], length=period)
                    self.logger.debug(f"SMA({period})を計算しました")
            except Exception as e:
                self.logger.error(f"SMA({period})の計算に失敗しました: {e}")
        
        return df
    
    def add_ema(self, df: pd.DataFrame, periods: Optional[List[int]] = None) -> pd.DataFrame:
        """
        指数移動平均（EMA）を計算して追加する
        
        Args:
            df: OHLCVデータフレーム
            periods: 期間のリスト（省略時は設定から取得）
        
        Returns:
            EMAが追加されたデータフレーム
        """
        if periods is None:
            periods = self.indicator_config.get('ema', {}).get('periods', [12, 26])
        
        for period in periods:
            column_name = f'ema_{period}'
            try:
                df[column_name] = ta.ema(df['close'], length=period)
                self.logger.debug(f"EMA({period})を計算しました")
            except Exception as e:
                self.logger.error(f"EMA({period})の計算に失敗しました: {e}")
        
        return df
    
    def add_macd(self, df: pd.DataFrame, fast: Optional[int] = None, 
                 slow: Optional[int] = None, signal: Optional[int] = None) -> pd.DataFrame:
        """
        MACD（移動平均収束拡散）を計算して追加する
        
        Args:
            df: OHLCVデータフレーム
            fast: 短期EMA期間（省略時は設定から取得）
            slow: 長期EMA期間（省略時は設定から取得）
            signal: シグナル期間（省略時は設定から取得）
        
        Returns:
            MACDが追加されたデータフレーム
        """
        macd_config = self.indicator_config.get('macd', {})
        if fast is None:
            fast = macd_config.get('fast_period', 12)
        if slow is None:
            slow = macd_config.get('slow_period', 26)
        if signal is None:
            signal = macd_config.get('signal_period', 9)
        
        try:
            macd_result = ta.macd(df['close'], fast=fast, slow=slow, signal=signal)
            df['macd'] = macd_result[f'MACD_{fast}_{slow}_{signal}']
            df['macd_signal'] = macd_result[f'MACDs_{fast}_{slow}_{signal}']
            df['macd_histogram'] = macd_result[f'MACDh_{fast}_{slow}_{signal}']
            self.logger.debug(f"MACD({fast},{slow},{signal})を計算しました")
        except Exception as e:
            self.logger.error(f"MACDの計算に失敗しました: {e}")
        
        return df
    
    def add_rsi(self, df: pd.DataFrame, period: Optional[int] = None) -> pd.DataFrame:
        """
        RSI（相対力指数）を計算して追加する
        
        Args:
            df: OHLCVデータフレーム
            period: 計算期間（省略時は設定から取得）
        
        Returns:
            RSIが追加されたデータフレーム
        """
        if period is None:
            period = self.indicator_config.get('rsi', {}).get('period', 14)
        
        try:
            df['rsi'] = ta.rsi(df['close'], length=period)
            self.logger.debug(f"RSI({period})を計算しました")
        except Exception as e:
            self.logger.error(f"RSIの計算に失敗しました: {e}")
        
        return df
    
    def add_bollinger_bands(self, df: pd.DataFrame, period: Optional[int] = None, 
                           num_std: Optional[float] = None) -> pd.DataFrame:
        """
        ボリンジャーバンドを計算して追加する
        
        Args:
            df: OHLCVデータフレーム
            period: 計算期間（省略時は設定から取得）
            num_std: 標準偏差の倍数（省略時は設定から取得）
        
        Returns:
            ボリンジャーバンドが追加されたデータフレーム
        """
        bb_config = self.indicator_config.get('bollinger_bands', {})
        if period is None:
            period = bb_config.get('period', 20)
        if num_std is None:
            num_std = bb_config.get('num_std', 2)
        
        try:
            bb_result = ta.bbands(df['close'], length=period, std=num_std)
            df['bb_upper'] = bb_result[f'BBU_{period}_{num_std}']
            df['bb_middle'] = bb_result[f'BBM_{period}_{num_std}']
            df['bb_lower'] = bb_result[f'BBL_{period}_{num_std}']
            df['bb_bandwidth'] = bb_result[f'BBB_{period}_{num_std}']
            df['bb_percent'] = bb_result[f'BBP_{period}_{num_std}']
            self.logger.debug(f"ボリンジャーバンド({period},{num_std})を計算しました")
        except Exception as e:
            self.logger.error(f"ボリンジャーバンドの計算に失敗しました: {e}")
        
        return df
    
    def add_atr(self, df: pd.DataFrame, period: Optional[int] = None) -> pd.DataFrame:
        """
        ATR（平均真幅）を計算して追加する
        
        Args:
            df: OHLCVデータフレーム
            period: 計算期間（省略時は設定から取得）
        
        Returns:
            ATRが追加されたデータフレーム
        """
        if period is None:
            period = self.indicator_config.get('atr', {}).get('period', 14)
        
        try:
            df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=period)
            self.logger.debug(f"ATR({period})を計算しました")
        except Exception as e:
            self.logger.error(f"ATRの計算に失敗しました: {e}")
        
        return df
    
    def add_stochastic(self, df: pd.DataFrame, k_period: int = 14, 
                      d_period: int = 3, smooth_k: int = 3) -> pd.DataFrame:
        """
        ストキャスティクスを計算して追加する
        
        Args:
            df: OHLCVデータフレーム
            k_period: %K期間
            d_period: %D期間
            smooth_k: %Kの平滑化期間
        
        Returns:
            ストキャスティクスが追加されたデータフレーム
        """
        try:
            stoch_result = ta.stoch(df['high'], df['low'], df['close'], 
                                   k=k_period, d=d_period, smooth_k=smooth_k)
            df['stoch_k'] = stoch_result[f'STOCHk_{k_period}_{d_period}_{smooth_k}']
            df['stoch_d'] = stoch_result[f'STOCHd_{k_period}_{d_period}_{smooth_k}']
            self.logger.debug(f"ストキャスティクス({k_period},{d_period},{smooth_k})を計算しました")
        except Exception as e:
            self.logger.error(f"ストキャスティクスの計算に失敗しました: {e}")
        
        return df
    
    def add_adx(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """
        ADX（平均方向性指数）を計算して追加する
        
        Args:
            df: OHLCVデータフレーム
            period: 計算期間
        
        Returns:
            ADXが追加されたデータフレーム
        """
        try:
            adx_result = ta.adx(df['high'], df['low'], df['close'], length=period)
            df['adx'] = adx_result[f'ADX_{period}']
            df['dmp'] = adx_result[f'DMP_{period}']
            df['dmn'] = adx_result[f'DMN_{period}']
            self.logger.debug(f"ADX({period})を計算しました")
        except Exception as e:
            self.logger.error(f"ADXの計算に失敗しました: {e}")
        
        return df
    
    def add_ichimoku(self, df: pd.DataFrame, tenkan: int = 9, kijun: int = 26, 
                    senkou_b: int = 52) -> pd.DataFrame:
        """
        一目均衡表を計算して追加する
        
        Args:
            df: OHLCVデータフレーム
            tenkan: 転換線期間
            kijun: 基準線期間
            senkou_b: 先行スパンB期間
        
        Returns:
            一目均衡表が追加されたデータフレーム
        """
        try:
            ichimoku_result = ta.ichimoku(df['high'], df['low'], df['close'], 
                                         tenkan=tenkan, kijun=kijun, senkou=senkou_b)
            
            # 列名を取得（pandas_taのバージョンによって異なる場合がある）
            for col in ichimoku_result[0].columns:
                if 'ISA' in col:
                    df['ichimoku_span_a'] = ichimoku_result[0][col]
                elif 'ISB' in col:
                    df['ichimoku_span_b'] = ichimoku_result[0][col]
                elif 'ITS' in col:
                    df['ichimoku_tenkan'] = ichimoku_result[0][col]
                elif 'IKS' in col:
                    df['ichimoku_kijun'] = ichimoku_result[0][col]
                elif 'ICS' in col:
                    df['ichimoku_chikou'] = ichimoku_result[0][col]
            
            self.logger.debug(f"一目均衡表({tenkan},{kijun},{senkou_b})を計算しました")
        except Exception as e:
            self.logger.error(f"一目均衡表の計算に失敗しました: {e}")
        
        return df
    
    def add_custom_indicator(self, df: pd.DataFrame, name: str, 
                           func: callable, **kwargs) -> pd.DataFrame:
        """
        カスタム指標を計算して追加する
        
        Args:
            df: OHLCVデータフレーム
            name: 指標名
            func: 計算関数
            **kwargs: 関数に渡す引数
        
        Returns:
            カスタム指標が追加されたデータフレーム
        """
        try:
            result = func(df, **kwargs)
            if isinstance(result, pd.Series):
                df[name] = result
            elif isinstance(result, pd.DataFrame):
                df = pd.concat([df, result], axis=1)
            else:
                self.logger.warning(f"カスタム指標{name}の戻り値が不正です")
            
            self.logger.debug(f"カスタム指標{name}を計算しました")
        except Exception as e:
            self.logger.error(f"カスタム指標{name}の計算に失敗しました: {e}")
        
        return df
    
    def validate_dataframe(self, df: pd.DataFrame) -> bool:
        """
        データフレームが指標計算に適しているか検証する
        
        Args:
            df: データフレーム
        
        Returns:
            検証結果
        """
        if df.empty:
            return False
        
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_columns):
            self.logger.error(f"必要な列が不足しています: {required_columns}")
            return False
        
        # NaNチェック
        if df[required_columns].isnull().any().any():
            self.logger.warning("データにNaNが含まれています")
            return False
        
        return True
    
    def calculate_dynamic_indicators(self, df: pd.DataFrame, strategy_params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        戦略パラメータに基づいて動的に指標を計算する
        
        Args:
            df: OHLCVデータフレーム
            strategy_params: 戦略パラメータ（移動平均期間など）
        
        Returns:
            指標が追加されたデータフレーム
        """
        result_df = df.copy()
        
        # 基本指標を計算
        result_df = self.calculate_all(result_df)
        
        if strategy_params is None:
            return result_df
        
        # 戦略パラメータから動的にSMAを追加
        sma_periods = []
        
        # MA Cross戦略のパラメータ
        if 'short_period' in strategy_params and 'long_period' in strategy_params:
            sma_periods.extend([strategy_params['short_period'], strategy_params['long_period']])
        
        # その他の戦略パラメータから期間を抽出
        for key, value in strategy_params.items():
            if key.endswith('_period') and isinstance(value, int) and value > 0:
                sma_periods.append(value)
        
        # 重複を除去
        sma_periods = list(set(sma_periods))
        
        if sma_periods:
            result_df = self.add_sma(result_df, sma_periods)
            self.logger.debug(f"戦略パラメータに基づいてSMA期間を追加: {sma_periods}")
        
        return result_df
