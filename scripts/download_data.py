"""
データダウンロードスクリプト

GMOコインから過去のOHLCVデータをダウンロードして保存するスクリプト
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
import argparse

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from backend.config_manager import get_config_manager
from backend.logger import get_logger
from backend.data_fetcher import GMOCoinRESTFetcher


async def download_historical_data(symbol: str, interval: str, days: int):
    """
    過去データをダウンロードする
    
    Args:
        symbol: 通貨ペア
        interval: 時間間隔
        days: 取得日数
    """
    logger = get_logger()
    logger.info(f"データダウンロード開始: {symbol} {interval} 過去{days}日分")
    
    async with GMOCoinRESTFetcher() as fetcher:
        # 日付範囲を計算
        end_date = datetime.now()
        current_date = end_date - timedelta(days=days)
        
        all_data = []
        
        # 1日ずつデータを取得
        while current_date < end_date:
            try:
                logger.info(f"取得中: {current_date.strftime('%Y-%m-%d')}")
                
                # データを取得
                df = await fetcher.fetch_ohlcv(
                    symbol=symbol,
                    interval=interval,
                    limit=1000  # 最大取得件数
                )
                
                if not df.empty:
                    all_data.append(df)
                
                # 次の日へ
                current_date += timedelta(days=1)
                
                # API制限を考慮して待機
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"データ取得エラー: {e}")
                continue
        
        logger.info(f"データダウンロード完了: {len(all_data)}日分")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='GMOコイン過去データダウンロード')
    parser.add_argument(
        '--symbol',
        default='BTC_JPY',
        help='通貨ペア (デフォルト: BTC_JPY)'
    )
    parser.add_argument(
        '--interval',
        default='1hour',
        choices=['1min', '5min', '15min', '30min', '1hour', '4hour', '8hour', '12hour', '1day'],
        help='時間間隔 (デフォルト: 1hour)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='取得日数 (デフォルト: 30日)'
    )
    
    args = parser.parse_args()
    
    # 非同期で実行
    asyncio.run(download_historical_data(
        args.symbol,
        args.interval,
        args.days
    ))


if __name__ == "__main__":
    main()
