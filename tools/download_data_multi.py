"""
改良版データダウンロードスクリプト

GMOコインから複数通貨ペア・複数期間のOHLCVデータをダウンロード
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


async def download_historical_data(symbol: str, interval: str, days: int = None):
    """
    過去データをダウンロードする
    
    Args:
        symbol: 通貨ペア
        interval: 時間間隔
        days: 取得日数（Noneの場合は最大限取得）
    """
    logger = get_logger()
    config = get_config_manager()
    logger.info(f"データダウンロード開始: {symbol} {interval}")
    
    async with GMOCoinRESTFetcher() as fetcher:
        try:
            # REST API fetcher の fetch_ohlcv メソッドを直接使用
            logger.info(f"GMOコインAPIからデータ取得中: {symbol} {interval}")
            
            # fetch_ohlcvメソッドを使用してデータを取得
            df = await fetcher.fetch_ohlcv(symbol=symbol, interval=interval, limit=1000)
            
            if df.empty:
                logger.warning("取得したデータが空でした")
                return False, 0, None, None
            
            logger.info(f"取得したデータ数: {len(df)}件")
            logger.info(f"期間: {df['timestamp'].min()} ～ {df['timestamp'].max()}")
            
            # データを保存（DataStorageを直接使用）
            storage = DataStorage(config)
            storage.save_ohlcv(symbol, interval, df)
            
            logger.info(f"データを保存しました: {symbol}_{interval}")
            return True, len(df), df['timestamp'].min(), df['timestamp'].max()
                
        except Exception as e:
            logger.error(f"データ取得エラー: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False, 0, None, None


async def download_multiple_pairs(pairs: list, intervals: list, days: int = None):
    """
    複数の通貨ペア・時間足でデータをダウンロード
    
    Args:
        pairs: 通貨ペアのリスト
        intervals: 時間間隔のリスト
        days: 取得日数
    """
    logger = get_logger()
    
    results = []
    
    for symbol in pairs:
        for interval in intervals:
            logger.info(f"\n{'='*50}")
            logger.info(f"開始: {symbol} - {interval}")
            logger.info('='*50)
            
            success, count, start_date, end_date = await download_historical_data(symbol, interval, days)
            
            results.append({
                'symbol': symbol,
                'interval': interval,
                'success': success,
                'count': count,
                'start_date': start_date,
                'end_date': end_date
            })
            
            # API制限を考慮して待機
            await asyncio.sleep(1)
    
    return results


def main():
    """メイン関数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='GMOコイン過去データダウンロード')
    parser.add_argument(
        '--symbols',
        nargs='+',
        default=['BTC_JPY'],
        help='通貨ペア（複数指定可能） 例: BTC_JPY ETH_JPY XRP_JPY'
    )
    parser.add_argument(
        '--intervals',
        nargs='+',
        default=['15min', '1hour'],
        choices=['1min', '5min', '15min', '30min', '1hour', '4hour', '8hour', '12hour', '1day', '1week', '1month'],
        help='時間間隔（複数指定可能） 例: 15min 1hour 4hour 1day'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=90,
        help='取得日数 (デフォルト: 90日) ※実際に取得できる期間はAPIの制限による'
    )
    
    args = parser.parse_args()
    
    # 非同期で実行
    results = asyncio.run(download_multiple_pairs(
        args.symbols,
        args.intervals,
        args.days
    ))
    
    # 結果を表示
    print(f"\n{'='*80}")
    print("📊 データダウンロード結果")
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
        print(f"\n💡 ヒント:")
        print(f"   - Streamlit UIでバックテストを実行できます")
        print(f"   - 複数の時間足を組み合わせた戦略も可能です")
        print(f"   - より長期間のデータが必要な場合は --days を増やしてください")


if __name__ == "__main__":
    main()
