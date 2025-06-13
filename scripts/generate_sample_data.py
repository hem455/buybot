"""
サンプルチャートデータ生成

デモ用にリアルなチャートデータを生成
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

from backend.config_manager import get_config_manager
from backend.data_fetcher.base import DataStorage
from backend.indicator import IndicatorCalculator


def generate_realistic_ohlcv(symbol: str, days: int = 30, interval: str = '1hour') -> pd.DataFrame:
    """リアルなOHLCVデータを生成"""
    
    # 時間間隔の設定
    if interval == '1min':
        periods = days * 24 * 60
        freq = 'T'
    elif interval == '5min':
        periods = days * 24 * 12
        freq = '5T'
    elif interval == '15min':
        periods = days * 24 * 4
        freq = '15T'
    elif interval == '30min':
        periods = days * 24 * 2
        freq = '30T'
    elif interval == '1hour':
        periods = days * 24
        freq = 'H'
    elif interval == '4hour':
        periods = days * 6
        freq = '4H'
    elif interval == '1day':
        periods = days
        freq = 'D'
    else:
        periods = days * 24
        freq = 'H'
    
    # 基準価格
    base_prices = {
        'BTC_JPY': 6500000,
        'ETH_JPY': 500000,
        'XRP_JPY': 60,
        'LTC_JPY': 12000
    }
    
    base_price = base_prices.get(symbol, 1000000)
    
    # タイムスタンプ生成
    timestamps = pd.date_range(end=datetime.now(), periods=periods, freq=freq)
    
    # 価格変動をシミュレート
    prices = []
    current_price = base_price
    
    # トレンドとボラティリティ
    trend = np.random.choice([-0.0001, 0, 0.0001])  # 長期トレンド
    
    for i in range(len(timestamps)):
        # 日中のボラティリティ変化
        hour = timestamps[i].hour
        if 9 <= hour <= 10 or 14 <= hour <= 15:  # 東京市場の活発な時間
            volatility = 0.003
        elif 22 <= hour <= 23 or 2 <= hour <= 3:  # ロンドン/NY市場
            volatility = 0.004
        else:
            volatility = 0.002
        
        # ランダムウォーク + トレンド
        change = np.random.normal(trend, volatility)
        current_price = current_price * (1 + change)
        
        # 時々大きな動き
        if np.random.random() < 0.05:  # 5%の確率
            spike = np.random.choice([-0.01, 0.01])
            current_price = current_price * (1 + spike)
        
        prices.append(current_price)
    
    # OHLCVデータ作成
    ohlcv_data = []
    
    for i, (timestamp, close_price) in enumerate(zip(timestamps, prices)):
        # 始値（前の終値に近い値）
        if i == 0:
            open_price = close_price * (1 + np.random.normal(0, 0.001))
        else:
            open_price = prices[i-1] * (1 + np.random.normal(0, 0.0005))
        
        # 高値・安値
        intrabar_volatility = np.random.uniform(0.001, 0.003)
        high_price = max(open_price, close_price) * (1 + abs(np.random.normal(0, intrabar_volatility)))
        low_price = min(open_price, close_price) * (1 - abs(np.random.normal(0, intrabar_volatility)))
        
        # ボリューム（価格変動と相関）
        price_change = abs(close_price - open_price) / open_price
        base_volume = np.random.uniform(10, 100)
        volume = base_volume * (1 + price_change * 50)  # 価格変動が大きいほどボリューム増
        
        ohlcv_data.append({
            'timestamp': timestamp,
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': volume
        })
    
    df = pd.DataFrame(ohlcv_data)
    df.set_index('timestamp', inplace=True)
    
    # テクニカル指標を計算
    indicator_calc = IndicatorCalculator()
    df = indicator_calc.calculate_all(df)
    
    return df


def save_sample_data():
    """サンプルデータを保存"""
    config = get_config_manager()
    storage = DataStorage(config)
    
    symbols = ['BTC_JPY', 'ETH_JPY', 'XRP_JPY', 'LTC_JPY']
    intervals = ['1hour', '4hour', '1day']
    
    for symbol in symbols:
        for interval in intervals:
            print(f"Generating {symbol} {interval} data...")
            
            # データ生成
            df = generate_realistic_ohlcv(symbol, days=90, interval=interval)
            
            # 保存
            storage.save_ohlcv(df, symbol, interval)
            print(f"Saved {len(df)} records for {symbol} {interval}")
    
    print("\nSample data generation completed!")


if __name__ == "__main__":
    save_sample_data()
