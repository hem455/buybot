"""
GMOコイン自動売買システム - メインエントリーポイント

システムの起動と管理を行うメインモジュール
"""

import asyncio
import signal
import sys
from pathlib import Path
from typing import Optional
import argparse
import subprocess
import os
import time

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent))

from backend.config_manager import get_config_manager
from backend.logger import get_logger
from backend.data_fetcher import GMOCoinRESTFetcher, GMOCoinWebSocketFetcher
from backend.indicator import IndicatorCalculator
from backend.strategy import get_strategy_manager
from backend.risk_manager import RiskManager
from backend.order_executor import OrderExecutor


class TradingBot:
    """自動売買ボットクラス"""
    
    def __init__(self):
        """初期化"""
        self.config = get_config_manager()
        self.logger = get_logger()
        self.running = False
        
        # コンポーネント
        self.rest_fetcher = GMOCoinRESTFetcher()
        self.ws_fetcher = GMOCoinWebSocketFetcher(self.config)
        self.indicator_calculator = IndicatorCalculator()
        self.strategy_manager = get_strategy_manager()
        self.risk_manager = RiskManager()
        self.order_executor = OrderExecutor()
        
        # 取引設定
        self.symbol = self.config.get('trading.symbol', 'BTC_JPY')
        self.interval = self.config.get('data_fetcher.ohlcv.default_interval', '1hour')
        
        self.logger.info("自動売買ボットを初期化しました")
    
    async def start(self):
        """ボットを開始"""
        self.logger.info("自動売買ボットを開始します")
        self.running = True
        
        try:
            # WebSocket接続を開始
            await self.ws_fetcher.connect()
            
            # メインループ
            while self.running:
                await self.trading_loop()
                
                # 次のループまで待機
                await asyncio.sleep(60)  # 1分ごとに実行
                
        except Exception as e:
            self.logger.error(f"ボットエラー: {e}")
        finally:
            await self.stop()
    
    async def trading_loop(self):
        """取引ループ"""
        try:
            # OHLCVデータを取得
            async with self.rest_fetcher as fetcher:
                df = await fetcher.fetch_ohlcv(self.symbol, self.interval)
                
                if df.empty:
                    self.logger.warning("データが取得できませんでした")
                    return
                
                # 指標を計算
                df = self.indicator_calculator.calculate_all(df)
                
                # 口座情報を取得
                balance_info = await fetcher.fetch_balance()
                positions = await fetcher.fetch_positions()
                
                # 現在のポジション
                current_position = None
                if positions:
                    # BTC/JPYのポジションを探す
                    for pos in positions:
                        if pos['symbol'] == self.symbol:
                            current_position = {
                                'side': 'LONG' if pos['side'] == 'BUY' else 'SHORT',
                                'size': pos['size'],
                                'entry_price': pos['price']
                            }
                            break
                
                # 口座情報
                total_jpy = balance_info.get('JPY', {}).get('amount', 0)
                account_info = {
                    'total_balance': total_jpy,
                    'available_balance': balance_info.get('JPY', {}).get('available', 0),
                    'margin_level': 1.0  # 現物取引なので100%
                }
                
                # リスク制限をチェック
                can_trade, reason = self.risk_manager.check_risk_limits(
                    account_info, 
                    [current_position] if current_position else []
                )
                
                if not can_trade:
                    self.logger.warning(f"取引制限: {reason}")
                    return
                
                # 戦略を実行
                strategy = self.strategy_manager.get_active_strategy()
                signal, details = strategy.generate_signal(df, current_position, account_info)
                
                # シグナルに基づいて取引
                if signal.value != "HOLD":
                    self.logger.info(f"シグナル発生: {signal.value} - {details}")
                    
                    # ポジションサイズを計算
                    position_size = 0
                    stop_loss = None
                    take_profit = None
                    
                    if signal.value in ["BUY", "SELL"]:
                        # ATRを取得
                        atr = df['atr'].iloc[-1] if 'atr' in df.columns else None
                        current_price = df['close'].iloc[-1]
                        
                        # ストップロスを計算
                        stop_loss = self.risk_manager.calculate_stop_loss(
                            signal, current_price, atr
                        )
                        
                        # ポジションサイズを計算
                        position_size = self.risk_manager.calculate_position_size(
                            signal, total_jpy, current_price, stop_loss
                        )
                        
                        # テイクプロフィットを計算
                        if stop_loss:
                            take_profit = self.risk_manager.calculate_take_profit(
                                signal, current_price, stop_loss
                            )
                    
                    # 注文を実行
                    if position_size > 0 or signal.value in ["CLOSE_LONG", "CLOSE_SHORT", "CLOSE_ALL"]:
                        result = await self.order_executor.execute_signal(
                            signal, position_size, stop_loss, take_profit
                        )
                        
                        if result['success']:
                            self.logger.info(f"注文実行成功: {result}")
                        else:
                            self.logger.error(f"注文実行失敗: {result['error']}")
                
        except Exception as e:
            self.logger.error(f"取引ループエラー: {e}")
    
    async def stop(self):
        """ボットを停止"""
        self.logger.info("自動売買ボットを停止します")
        self.running = False
        
        # WebSocket接続を切断
        if self.ws_fetcher:
            await self.ws_fetcher.disconnect()
        
        # すべての注文をキャンセル
        await self.order_executor.cancel_all_orders()
        
        self.logger.info("自動売買ボットを停止しました")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='GMOコイン自動売買システム')
    parser.add_argument(
        '--mode',
        choices=['bot', 'ui', 'both'],
        default='ui',
        help='実行モード: bot (ボットのみ), ui (UIのみ), both (両方)'
    )
    parser.add_argument(
        '--config',
        default='config/config.yaml',
        help='設定ファイルのパス'
    )
    
    args = parser.parse_args()
    
    # ロガーを取得
    logger = get_logger()
    
    if args.mode in ['bot', 'both']:
        # ボットを起動
        bot = TradingBot()
        
        # シグナルハンドラーを設定
        def signal_handler(sig, frame):
            logger.info("終了シグナルを受信しました")
            asyncio.create_task(bot.stop())
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # 非同期でボットを実行
        if args.mode == 'bot':
            asyncio.run(bot.start())
        else:
            # UIと並行して実行
            import threading
            bot_thread = threading.Thread(
                target=lambda: asyncio.run(bot.start()),
                daemon=True
            )
            bot_thread.start()
    
    if args.mode in ['ui', 'both']:
        # StreamlitのUIを起動
        streamlit_cmd = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(Path(__file__).parent / "frontend" / "app.py"),
            "--server.port", "8501",
            "--server.address", "0.0.0.0"
        ]
        
        # 環境変数を設定
        env = os.environ.copy()
        env['PYTHONPATH'] = str(Path(__file__).parent)
        
        # Streamlitを起動
        logger.info("Streamlit UIを起動します")
        logger.info("\nStreamlitアプリケーションにアクセスするには：")
        logger.info("  http://localhost:8501")
        logger.info("  http://127.0.0.1:8501\n")
        
        # subprocess.runを使用してブロッキング実行
        subprocess.run(streamlit_cmd, env=env)


if __name__ == "__main__":
    main()
