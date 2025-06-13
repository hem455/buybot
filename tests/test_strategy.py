"""
Strategyモジュールのテスト
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backend.strategy import Signal, SimpleMovingAverageCrossStrategy, MACDRSIStrategy


class TestSimpleMovingAverageCrossStrategy:
    
    @pytest.fixture
    def sample_data(self):
        """テスト用のサンプルデータを作成"""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='H')
        
        # トレンドを持つ価格データを生成
        np.random.seed(42)
        trend = np.linspace(45000, 50000, 100)
        noise = np.random.normal(0, 100, 100)
        prices = trend + noise
        
        df = pd.DataFrame({
            'timestamp': dates,
            'open': prices * 0.99,
            'high': prices * 1.01,
            'low': prices * 0.98,
            'close': prices,
            'volume': np.random.uniform(1, 10, 100)
        })
        
        # 移動平均を計算
        df['sma_7'] = df['close'].rolling(window=7).mean()
        df['sma_25'] = df['close'].rolling(window=25).mean()
        
        return df
    
    def test_strategy_initialization(self):
        """戦略の初期化テスト"""
        strategy = SimpleMovingAverageCrossStrategy()
        
        assert strategy.short_period == 7
        assert strategy.long_period == 25
        assert strategy.confirmation_bars == 1
    
    def test_buy_signal(self, sample_data):
        """買いシグナルのテスト"""
        strategy = SimpleMovingAverageCrossStrategy()
        
        # ゴールデンクロスを作成
        df = sample_data.copy()
        df.loc[95, 'sma_7'] = df.loc[95, 'sma_25'] - 100
        df.loc[96, 'sma_7'] = df.loc[96, 'sma_25'] + 100
        
        signal, details = strategy.generate_signal(
            df.iloc[:97],
            current_position=None,
            account_info={'total_balance': 1000000}
        )
        
        assert signal == Signal.BUY
        assert 'ゴールデンクロス' in details['reason']
    
    def test_sell_signal(self, sample_data):
        """売りシグナルのテスト"""
        strategy = SimpleMovingAverageCrossStrategy()
        
        # デッドクロスを作成
        df = sample_data.copy()
        df.loc[95, 'sma_7'] = df.loc[95, 'sma_25'] + 100
        df.loc[96, 'sma_7'] = df.loc[96, 'sma_25'] - 100
        
        signal, details = strategy.generate_signal(
            df.iloc[:97],
            current_position=None,
            account_info={'total_balance': 1000000}
        )
        
        assert signal == Signal.SELL
        assert 'デッドクロス' in details['reason']


class TestMACDRSIStrategy:
    
    @pytest.fixture
    def sample_data_with_indicators(self):
        """指標付きのサンプルデータを作成"""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='H')
        
        # 価格データを生成
        np.random.seed(42)
        prices = 45000 + np.cumsum(np.random.normal(0, 100, 100))
        
        df = pd.DataFrame({
            'timestamp': dates,
            'open': prices * 0.99,
            'high': prices * 1.01,
            'low': prices * 0.98,
            'close': prices,
            'volume': np.random.uniform(1, 10, 100)
        })
        
        # 簡易的な指標を計算
        df['macd'] = np.random.normal(0, 50, 100)
        df['macd_signal'] = df['macd'].rolling(window=9).mean()
        df['macd_histogram'] = df['macd'] - df['macd_signal']
        df['rsi'] = np.random.uniform(20, 80, 100)
        
        return df
    
    def test_strategy_initialization(self):
        """戦略の初期化テスト"""
        strategy = MACDRSIStrategy()
        
        assert strategy.rsi_oversold == 30
        assert strategy.rsi_overbought == 70
        assert strategy.macd_threshold == 0
    
    def test_buy_signal_with_rsi_oversold(self, sample_data_with_indicators):
        """RSI売られすぎでの買いシグナルテスト"""
        strategy = MACDRSIStrategy()
        
        df = sample_data_with_indicators.copy()
        
        # 買い条件を設定
        df.loc[98, 'rsi'] = 25  # 売られすぎ
        df.loc[97, 'macd_histogram'] = -10
        df.loc[98, 'macd_histogram'] = 10  # 正に転換
        df.loc[98, 'macd'] = 20
        
        signal, details = strategy.generate_signal(
            df.iloc[:99],
            current_position=None,
            account_info={'total_balance': 1000000}
        )
        
        assert signal == Signal.BUY
        assert 'RSI売られすぎ' in details['reason']
