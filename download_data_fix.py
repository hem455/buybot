"""
修正版データダウンロードスクリプト

GMOコインから過去のOHLCVデータをダウンロードして保存する
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent))

from backend.config_manager import get_config_manager
from backend.logger import get_logger
from backend.data_fetcher import GMOCoinRESTFetcher
from backend.data_fetcher.base import DataStorage


async def download_historical_data(symbol: str, interval: str, days: int):
    """
    過去データをダウンロードする
    
    Args:
        symbol: 通貨ペア
        interval: 時間間隔
        days: 取得日数
    """
    logger = get_logger()
    config = get_config_manager()
    logger.info(f"データダウンロード開始: {symbol} {interval} 過去{days}日分")
    
    async with GMOCoinRESTFetcher() as fetcher:
        # 全データを格納
        all_data = []
        
        try:
            # GMOコインAPIで過去データを取得
            # 最大1000件ずつ取得可能
            logger.info(f"GMOコインAPIからデータを取得中...")
            
            # データを取得（GMOコインは最新のデータから遡って取得）
            df = await fetcher.fetch_ohlcv(
                symbol=symbol,
                interval=interval,
                limit=1000  # 最大取得件数
            )
            
            if not df.empty:
                logger.info(f"取得したデータ数: {len(df)}件")
                logger.info(f"期間: {df['timestamp'].min()} ～ {df['timestamp'].max()}")
                
                # データをParquet形式で保存
                storage = DataStorage(config)
                storage.save_ohlcv(df, symbol, interval)
                
                logger.info(f"データを保存しました: {symbol}_{interval}")
                return True
            else:
                logger.error("データが取得できませんでした")
                return False
                
        except Exception as e:
            logger.error(f"データ取得エラー: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False


def main():
    """メイン関数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='GMOコイン過去データダウンロード')
    parser.add_argument(
        '--symbol',
        default='BTC_JPY',
        help='通貨ペア (デフォルト: BTC_JPY)'
    )
    parser.add_argument(
        '--interval',
        default='1hour',
        choices=['1min', '5min', '15min', '30min', '1hour', '4hour', '8hour', '12hour', '1day', '1week', '1month'],
        help='時間間隔 (デフォルト: 1hour)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='取得日数 (デフォルト: 30日) ※実際にはAPIの制限により最大1000件'
    )
    
    args = parser.parse_args()
    
    # 非同期で実行
    success = asyncio.run(download_historical_data(
        args.symbol,
        args.interval,
        args.days
    ))
    
    if success:
        print(f"\n✅ データダウンロード完了！")
        print(f"📁 保存先: ./data/ohlcv/{args.symbol}_{args.interval}.parquet")
        print(f"💡 Streamlit UIでバックテストを実行できます")
    else:
        print(f"\n❌ データダウンロードに失敗しました")
        print(f"⚠️  .envファイルにAPIキーが設定されているか確認してください")


if __name__ == "__main__":
    main()
