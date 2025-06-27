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
            # GMOコインAPIで過去データを取得
            # GMOコインのklines APIは、指定日の全データを返す
            # 複数日のデータを取得するには、日付を変えて複数回リクエストする必要がある
            
            all_data = []
            current_date = datetime.now()
            
            # 過去何日分のデータを取得するか
            if days is None:
                # 最大365日分を試みる
                days = 365
            
            successful_days = 0
            
            for i in range(days):
                # 日付を遡る
                target_date = current_date - timedelta(days=i)
                
                # パラメータを設定
                params = {
                    'symbol': symbol,
                    'interval': interval,
                    'date': target_date.strftime('%Y%m%d')
                }
                
                try:
                    # データを取得
                    logger.info(f"取得中: {target_date.strftime('%Y-%m-%d')}")
                    data = await fetcher._request('GET', '/v1/klines', params)
                    
                    if data:
                        # DataFrameに変換（GMOコインのレスポンス形式に合わせる）
                        df_day = pd.DataFrame(data, columns=['openTime', 'open', 'high', 'low', 'close', 'volume'])
                        # GMOコインのopenTimeはISO 8601文字列形式
                        df_day['timestamp'] = pd.to_datetime(df_day['openTime'], utc=True)
                        df_day['open'] = df_day['open'].astype(float)
                        df_day['high'] = df_day['high'].astype(float)
                        df_day['low'] = df_day['low'].astype(float)
                        df_day['close'] = df_day['close'].astype(float)
                        df_day['volume'] = df_day['volume'].astype(float)
                        df_day = df_day.drop(columns=['openTime'])
                        
                        all_data.append(df_day)
                        successful_days += 1
                        
                        # API制限を考慮
                        await asyncio.sleep(0.2)
                    
                except Exception as e:
                    # エラーが出た場合は継続
                    logger.error(f"{target_date.strftime('%Y-%m-%d')}のデータ取得失敗: {e}")
                    continue
                
                # 30日分取得したら一旦チェック
                if successful_days > 0 and successful_days % 30 == 0:
                    logger.info(f"{successful_days}日分のデータを取得済み")
            
            if all_data:
                # データを結合
                df = pd.concat(all_data, ignore_index=True)
                df = df.sort_values('timestamp')
                df = df.drop_duplicates(subset=['timestamp'])
                
                logger.info(f"取得したデータ数: {len(df)}件")
                logger.info(f"期間: {df['timestamp'].min()} ～ {df['timestamp'].max()}")
                
                # データを保存
                storage = DataStorage(config)
                storage.save_ohlcv(symbol, interval, df)
                
                logger.info(f"データを保存しました: {symbol}_{interval}")
                return True, len(df), df['timestamp'].min(), df['timestamp'].max()
            else:
                logger.error("データが取得できませんでした")
                return False, 0, None, None
                
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
        default=['1hour'],
        choices=['1min', '5min', '15min', '30min', '1hour', '4hour', '8hour', '12hour', '1day', '1week', '1month'],
        help='時間間隔（複数指定可能） 例: 1hour 4hour 1day'
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
