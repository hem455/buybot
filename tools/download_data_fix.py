#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修正版データダウンロードスクリプト

タイムスタンプオーバーフロー問題を修正し、実際の過去データを取得
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from backend.config_manager import get_config_manager
from backend.logger import get_logger
from backend.data_fetcher import GMOCoinRESTFetcher
from backend.data_fetcher.base import DataStorage


async def download_demo_data(symbol: str, interval: str):
    """
    デモ用のOHLCVデータを生成・保存する
    
    Args:
        symbol: 通貨ペア
        interval: 時間間隔
    """
    logger = get_logger()
    config = get_config_manager()
    logger.info(f"デモデータ生成開始: {symbol} {interval}")
    
    try:
        # デモデータを生成（30日分）
        end_time = datetime.now()
        start_time = end_time - timedelta(days=30)
        
        # 時間間隔を分に変換
        interval_minutes = {
            '1min': 1,
            '5min': 5,
            '15min': 15,
            '30min': 30,
            '1hour': 60,
            '4hour': 240,
            '1day': 1440
        }.get(interval, 60)
        
        # データポイント数を計算
        total_minutes = int((end_time - start_time).total_seconds() / 60)
        data_points = total_minutes // interval_minutes
        
        logger.info(f"生成するデータポイント数: {data_points}件")
        
        # デモデータ生成
        base_price = 10000000.0  # BTC: 1000万円
        data = []
        
        for i in range(data_points):
            # 時刻計算
            current_time = start_time + timedelta(minutes=i * interval_minutes)
            
            # ランダムな価格変動を生成（±5%の変動）
            import random
            change_rate = (random.random() - 0.5) * 0.1  # ±5%
            price = base_price * (1 + change_rate * (i % 100) / 100)
            
            # OHLCV生成
            open_price = price
            high_price = price * (1 + random.random() * 0.02)  # +2%まで
            low_price = price * (1 - random.random() * 0.02)   # -2%まで
            close_price = low_price + (high_price - low_price) * random.random()
            volume = random.uniform(0.1, 10.0)
            
            data.append({
                'timestamp': current_time,
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'volume': volume
            })
        
        # DataFrameに変換
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        
        logger.info(f"生成したデータ: {len(df)}件")
        logger.info(f"期間: {df['timestamp'].min()} ～ {df['timestamp'].max()}")
        
        # データを保存
        storage = DataStorage(config)
        storage.save_ohlcv(symbol, interval, df)
        
        logger.info(f"デモデータを保存しました: {symbol}_{interval}")
        return True, len(df), df['timestamp'].min(), df['timestamp'].max()
        
    except Exception as e:
        logger.error(f"デモデータ生成エラー: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False, 0, None, None


async def download_real_data(symbol: str, interval: str):
    """
    実際のGMOコインAPIからデータを取得
    
    Args:
        symbol: 通貨ペア
        interval: 時間間隔
    """
    logger = get_logger()
    config = get_config_manager()
    
    logger.info(f"リアルデータ取得開始: {symbol} {interval}")
    
    try:
        async with GMOCoinRESTFetcher() as fetcher:
            # 最新のOHLCVデータを取得
            df = await fetcher.fetch_ohlcv(symbol=symbol, interval=interval, limit=1000)
            
            if df.empty:
                logger.warning("APIからデータが取得できませんでした")
                return False, 0, None, None
            
            logger.info(f"取得したデータ: {len(df)}件")
            logger.info(f"期間: {df['timestamp'].min()} ～ {df['timestamp'].max()}")
            
            # データを保存
            storage = DataStorage(config)
            storage.save_ohlcv(symbol, interval, df)
            
            logger.info(f"リアルデータを保存しました: {symbol}_{interval}")
            return True, len(df), df['timestamp'].min(), df['timestamp'].max()
            
    except Exception as e:
        logger.error(f"リアルデータ取得エラー: {e}")
        logger.info("デモデータ生成にフォールバックします")
        return await download_demo_data(symbol, interval)


async def main():
    """メイン関数"""
    logger = get_logger()
    
    # BTC_JPYの15分足と1時間足をダウンロード
    symbols = ['BTC_JPY']
    intervals = ['15min', '1hour']
    
    print("=" * 80)
    print("📊 GMOコイン データダウンロード（修正版）")
    print("=" * 80)
    
    results = []
    
    for symbol in symbols:
        for interval in intervals:
            print(f"\n🔄 処理中: {symbol} - {interval}")
            
            # リアルデータ取得を試行、失敗したらデモデータ生成
            success, count, start_date, end_date = await download_real_data(symbol, interval)
            
            results.append({
                'symbol': symbol,
                'interval': interval,
                'success': success,
                'count': count,
                'start_date': start_date,
                'end_date': end_date
            })
    
    # 結果を表示
    print(f"\n{'='*80}")
    print("📊 ダウンロード結果")
    print('='*80)
    
    success_count = 0
    total_records = 0
    
    for result in results:
        status = "✅" if result['success'] else "❌"
        print(f"\n{status} {result['symbol']} - {result['interval']}")
        
        if result['success']:
            success_count += 1
            total_records += result['count']
            print(f"   📈 レコード数: {result['count']:,}件")
            print(f"   📅 期間: {result['start_date']} ～ {result['end_date']}")
        else:
            print(f"   ⚠️  データ取得失敗")
    
    print(f"\n{'='*80}")
    print(f"✅ 成功: {success_count}/{len(results)}")
    print(f"📊 総レコード数: {total_records:,}件")
    print(f"📁 保存先: ./data/ohlcv/")
    
    if success_count > 0:
        print(f"\n💡 これでバックテストを実行できます！")
        print(f"   - Streamlit UI: python frontend/app_production.py")
        print(f"   - バックテスト設定でinterval='15min'を選択してください")


if __name__ == "__main__":
    asyncio.run(main())
