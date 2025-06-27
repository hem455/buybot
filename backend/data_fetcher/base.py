"""
データ取得モジュール - 基底クラス

GMOコインAPIからのデータ取得を管理する基底クラス。
REST APIとWebSocket APIの両方に対応。
"""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import pandas as pd

from ..config_manager import get_config_manager
from ..logger import get_logger


class BaseDataFetcher(ABC):
    """データ取得基底クラス"""
    
    def __init__(self):
        """初期化"""
        self.config = get_config_manager()
        self.logger = get_logger()
        self.exchange_config = self.config.get_exchange_config()
        self.trading_config = self.config.get_trading_config()
        self.rate_limiter = RateLimiter(self.config)
    
    @abstractmethod
    async def fetch_ohlcv(self, symbol: str, interval: str, limit: int = 100) -> pd.DataFrame:
        """OHLCVデータを取得する"""
        pass
    
    @abstractmethod
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """ティッカー情報を取得する"""
        pass
    
    @abstractmethod
    async def fetch_orderbook(self, symbol: str) -> Dict[str, Any]:
        """オーダーブック情報を取得する"""
        pass
    
    @abstractmethod
    async def fetch_balance(self) -> Dict[str, Any]:
        """口座残高を取得する"""
        pass
    
    @abstractmethod
    async def fetch_positions(self) -> List[Dict[str, Any]]:
        """ポジション情報を取得する"""
        pass


class RateLimiter:
    """APIレート制限管理クラス"""
    
    def __init__(self, config):
        """初期化"""
        self.config = config
        self.public_calls = []
        self.private_calls = []
        
        # レート制限設定を取得
        rate_config = config.get('data_fetcher.rate_limit', {})
        self.public_rps = rate_config.get('public_api', {}).get('requests_per_second', 10)
        self.public_rpm = rate_config.get('public_api', {}).get('requests_per_minute', 600)
        self.private_rps = rate_config.get('private_api', {}).get('requests_per_second', 10)
        self.private_rpm = rate_config.get('private_api', {}).get('requests_per_minute', 300)
    
    async def check_rate_limit(self, is_private: bool = False) -> None:
        """
        レート制限をチェックし、必要に応じて待機する
        
        Args:
            is_private: プライベートAPIかどうか
        """
        current_time = time.time()
        
        if is_private:
            calls = self.private_calls
            rps = self.private_rps
            rpm = self.private_rpm
        else:
            calls = self.public_calls
            rps = self.public_rps
            rpm = self.public_rpm
        
        # 古い記録を削除
        calls[:] = [t for t in calls if current_time - t < 60]
        
        # 秒間レート制限チェック
        recent_second_calls = [t for t in calls if current_time - t < 1]
        if len(recent_second_calls) >= rps:
            wait_time = 1 - (current_time - recent_second_calls[0])
            if wait_time > 0:
                await asyncio.sleep(wait_time)
        
        # 分間レート制限チェック
        if len(calls) >= rpm:
            wait_time = 60 - (current_time - calls[0])
            if wait_time > 0:
                await asyncio.sleep(wait_time)
        
        # 呼び出し記録を追加
        calls.append(current_time)


class DataValidator:
    """データ検証クラス"""
    
    @staticmethod
    def validate_ohlcv(df: pd.DataFrame) -> bool:
        """
        OHLCVデータを検証する
        
        Args:
            df: OHLCVデータフレーム
        
        Returns:
            検証結果
        """
        if df.empty:
            return False
        
        required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_columns):
            return False
        
        # 価格の整合性チェック
        if not all(df['low'] <= df['high']):
            return False
        
        if not all((df['low'] <= df['open']) & (df['open'] <= df['high'])):
            return False
        
        if not all((df['low'] <= df['close']) & (df['close'] <= df['high'])):
            return False
        
        # ボリュームが負でないことを確認
        if not all(df['volume'] >= 0):
            return False
        
        return True
    
    @staticmethod
    def validate_ticker(ticker: Dict[str, Any]) -> bool:
        """
        ティッカーデータを検証する
        
        Args:
            ticker: ティッカーデータ
        
        Returns:
            検証結果
        """
        required_fields = ['ask', 'bid', 'last', 'timestamp']
        if not all(field in ticker for field in required_fields):
            return False
        
        # 価格の整合性チェック
        if ticker['bid'] > ticker['ask']:
            return False
        
        return True
    
    @staticmethod
    def validate_orderbook(orderbook: Dict[str, Any]) -> bool:
        """
        オーダーブックデータを検証する
        
        Args:
            orderbook: オーダーブックデータ
        
        Returns:
            検証結果
        """
        if 'asks' not in orderbook or 'bids' not in orderbook:
            return False
        
        # 各注文が価格と数量を持っていることを確認
        for ask in orderbook['asks']:
            if len(ask) < 2 or ask[0] <= 0 or ask[1] <= 0:
                return False
        
        for bid in orderbook['bids']:
            if len(bid) < 2 or bid[0] <= 0 or bid[1] <= 0:
                return False
        
        # Ask価格がBid価格より高いことを確認
        if orderbook['asks'] and orderbook['bids']:
            if orderbook['asks'][0][0] <= orderbook['bids'][0][0]:
                return False
        
        return True


class DataStorage:
    """データ永続化管理クラス"""
    
    def __init__(self, config):
        """初期化"""
        self.config = config
        self.logger = get_logger()
        self.data_dir = config.get('data_fetcher.ohlcv.data_dir', './data/ohlcv')
        self._ensure_data_dir()
    
    def _ensure_data_dir(self):
        """データディレクトリを確保する"""
        from pathlib import Path
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
    
    def save_ohlcv(self, symbol: str, interval: str, df: pd.DataFrame) -> None:
        """
        OHLCVデータを保存する
        
        Args:
            symbol: 通貨ペア
            interval: 時間間隔
            df: データフレーム
        """
        if df.empty:
            return
        
        # ファイル名を生成
        filename = f"{symbol.replace('/', '_')}_{interval}.parquet"
        filepath = f"{self.data_dir}/{filename}"
        
        try:
            # 既存データがある場合は読み込んで結合
            if pd.io.common.file_exists(filepath):
                existing_df = pd.read_parquet(filepath)
                # タイムスタンプでソートして重複を削除
                df = pd.concat([existing_df, df]).drop_duplicates(subset=['timestamp']).sort_values('timestamp')
            
            # Parquet形式で保存
            df.to_parquet(filepath, index=False)
            self.logger.debug(f"OHLCVデータを保存しました: {filepath}")
            
        except Exception as e:
            self.logger.error(f"OHLCVデータの保存に失敗しました: {e}")
    
    def load_ohlcv(self, symbol: str, interval: str, 
                   start_time: Optional[datetime] = None, 
                   end_time: Optional[datetime] = None) -> pd.DataFrame:
        """
        OHLCVデータを読み込む
        
        Args:
            symbol: 通貨ペア
            interval: 時間間隔
            start_time: 開始時刻
            end_time: 終了時刻
        
        Returns:
            データフレーム（timestampがインデックス）
        """
        filename = f"{symbol.replace('/', '_')}_{interval}.parquet"
        filepath = f"{self.data_dir}/{filename}"
        
        try:
            if not pd.io.common.file_exists(filepath):
                self.logger.warning(f"OHLCVデータファイルが見つかりません: {filepath}")
                return pd.DataFrame()
            
            # Parquet形式で読み込み
            df = pd.read_parquet(filepath)
            
            if df.empty:
                return pd.DataFrame()
            
            # timestampをdatetime型に変換してインデックスに設定
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
                df = df.set_index('timestamp').sort_index()
            
            # 時刻でフィルタリング（インデックスベース）
            # フィルタ前に "naive → UTC" を揃える（ユーザー指摘の修正）
            if start_time:
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=timezone.utc)
                df = df[df.index >= start_time]
            if end_time:
                if end_time.tzinfo is None:
                    end_time = end_time.replace(tzinfo=timezone.utc)
                df = df[df.index <= end_time]
            
            return df
            
        except Exception as e:
            self.logger.error(f"OHLCVデータの読み込みに失敗しました: {e}")
            return pd.DataFrame()
