"""
GMOコイン REST API データ取得モジュール

GMOコインのREST APIを使用してデータを取得するモジュール。
"""

import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import pandas as pd
import aiohttp

from .base import BaseDataFetcher, DataValidator, DataStorage
from ..logger import get_logger, log_error


class GMOCoinRESTFetcher(BaseDataFetcher):
    """GMOコイン REST API データ取得クラス"""
    
    def __init__(self):
        """初期化"""
        super().__init__()
        self.base_url = self.exchange_config.get('rest_endpoint', 'https://api.coin.z.com/public')
        self.private_url = self.exchange_config.get('private_endpoint', 'https://api.coin.z.com/private')
        self.credentials = self.config.get_api_credentials()
        self.validator = DataValidator()
        self.storage = DataStorage(self.config)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """非同期コンテキストマネージャーの開始"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同期コンテキストマネージャーの終了"""
        if self.session:
            await self.session.close()
    
    def _generate_signature(self, timestamp: str, method: str, path: str, body: str = '') -> str:
        """
        APIシグネチャを生成する
        
        Args:
            timestamp: タイムスタンプ
            method: HTTPメソッド
            path: APIパス
            body: リクエストボディ
        
        Returns:
            シグネチャ
        """
        text = timestamp + method + path + body
        signature = hmac.new(
            bytes(self.credentials['api_secret'], 'ascii'),
            bytes(text, 'ascii'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, 
                      is_private: bool = False) -> Dict[str, Any]:
        """
        APIリクエストを送信する
        
        Args:
            method: HTTPメソッド
            endpoint: エンドポイント
            params: パラメータ
            is_private: プライベートAPIかどうか
        
        Returns:
            レスポンスデータ
        """
        # レート制限チェック
        await self.rate_limiter.check_rate_limit(is_private)
        
        # URLを構築
        if is_private:
            url = f"{self.private_url}{endpoint}"
        else:
            url = f"{self.base_url}{endpoint}"
        
        # ヘッダーを構築
        headers = {'Content-Type': 'application/json'}
        
        if is_private:
            timestamp = str(int(time.time() * 1000))
            body = json.dumps(params) if params and method != 'GET' else ''
            
            headers.update({
                'API-KEY': self.credentials['api_key'],
                'API-TIMESTAMP': timestamp,
                'API-SIGN': self._generate_signature(timestamp, method, endpoint, body)
            })
        
        # リクエストを送信
        start_time = time.time()
        
        try:
            if method == 'GET':
                async with self.session.get(url, params=params, headers=headers) as response:
                    data = await response.json()
                    status_code = response.status
            elif method == 'POST':
                async with self.session.post(url, json=params, headers=headers) as response:
                    data = await response.json()
                    status_code = response.status
            else:
                raise ValueError(f"サポートされていないHTTPメソッド: {method}")
            
            # レスポンス時間を記録
            response_time = time.time() - start_time
            self.logger.debug(f"API呼び出し | {method} {endpoint} | ステータス: {status_code} | 応答時間: {response_time:.3f}秒")
            
            # エラーチェック
            if status_code != 200:
                error_msg = data.get('messages', [{'message_string': 'Unknown error'}])[0]['message_string']
                raise Exception(f"APIエラー: {error_msg} (ステータス: {status_code})")
            
            if data.get('status') != 0:
                error_msg = data.get('messages', [{'message_string': 'Unknown error'}])[0]['message_string']
                raise Exception(f"APIエラー: {error_msg}")
            
            return data.get('data', {})
            
        except Exception as e:
            log_error('API_REQUEST_ERROR', str(e), {
                'endpoint': endpoint,
                'method': method,
                'is_private': is_private
            })
            raise
    
    async def fetch_ohlcv(self, symbol: str = None, interval: str = '1hour', limit: int = 100) -> pd.DataFrame:
        """
        OHLCVデータを取得する
        
        Args:
            symbol: 通貨ペア（省略時は設定から取得）
            interval: 時間間隔（1min, 5min, 10min, 15min, 30min, 1hour, 4hour, 8hour, 12hour, 1day, 1week, 1month）
            limit: 取得件数
        
        Returns:
            OHLCVデータフレーム
        """
        if symbol is None:
            symbol = self.trading_config.get('symbol', 'BTC_JPY')
        
        # インターバルをGMOコインAPIの形式に変換
        interval_map = {
            '1min': '1min',
            '5min': '5min',
            '15min': '15min',
            '30min': '30min',
            '1hour': '1hour',
            '4hour': '4hour',
            '8hour': '8hour',
            '12hour': '12hour',
            '1day': '1day',
            '1week': '1week',
            '1month': '1month'
        }
        
        if interval not in interval_map:
            raise ValueError(f"サポートされていないインターバル: {interval}")
        
        params = {
            'symbol': symbol,
            'interval': interval_map[interval]
        }
        
        try:
            # GMOコインのklines エンドポイントを使用
            data = await self._request('GET', '/v1/klines', params)
            
            if not data:
                self.logger.warning(f"OHLCVデータが取得できませんでした: {symbol} {interval}")
                return pd.DataFrame()
            
            # GMOコインのレスポンス形式: [[openTime, open, high, low, close, volume], ...]
            # カラム名を手動で付与
            COLS = ["open_time", "open", "high", "low", "close", "volume"]
            df = pd.DataFrame(data, columns=COLS)
            
            if df.empty:
                self.logger.warning(f"OHLCVデータが空でした: {symbol} {interval}")
                return pd.DataFrame()
            
            # timestampカラムを作成（ISO 8601形式の文字列をUTCで変換）
            df['timestamp'] = pd.to_datetime(df['open_time'], utc=True)
            
            # 数値カラムをfloat型に変換
            df[['open', 'high', 'low', 'close', 'volume']] = \
                df[['open', 'high', 'low', 'close', 'volume']].astype(float)
            
            # timestampをインデックスに設定してソート
            df = df.set_index('timestamp').sort_index()
            
            # open_timeカラムは不要なので削除
            df = df.drop(columns=['open_time'])
            
            # データを検証
            # 検証用にtimestampをカラムとして復元
            df_for_validation = df.reset_index()
            
            if self.validator.validate_ohlcv(df_for_validation):
                # データを保存（indexをリセットしてからsave）
                self.storage.save_ohlcv(symbol, interval, df_for_validation)
                return df.tail(limit)
            else:
                self.logger.error("OHLCVデータの検証に失敗しました")
                return pd.DataFrame()
                
        except Exception as e:
            self.logger.error(f"OHLCVデータの取得に失敗しました: {e}")
            return pd.DataFrame()
    
    async def fetch_ticker(self, symbol: str = None) -> Dict[str, Any]:
        """
        ティッカー情報を取得する
        
        Args:
            symbol: 通貨ペア（省略時は設定から取得）
        
        Returns:
            ティッカー情報
        """
        if symbol is None:
            symbol = self.trading_config.get('symbol', 'BTC_JPY')
        
        params = {'symbol': symbol}
        
        try:
            data = await self._request('GET', '/v1/ticker', params)
            
            if not data:
                return {}
            
            # 必要な情報を抽出
            ticker = {
                'symbol': symbol,
                'ask': float(data[0]['ask']),
                'bid': float(data[0]['bid']),
                'last': float(data[0]['last']),
                'volume': float(data[0]['volume']),
                'timestamp': datetime.now(timezone.utc)
            }
            
            # データを検証
            if self.validator.validate_ticker(ticker):
                return ticker
            else:
                self.logger.error("ティッカーデータの検証に失敗しました")
                return {}
                
        except Exception as e:
            self.logger.error(f"ティッカー情報の取得に失敗しました: {e}")
            return {}
    
    async def fetch_orderbook(self, symbol: str = None) -> Dict[str, Any]:
        """
        オーダーブック情報を取得する
        
        Args:
            symbol: 通貨ペア（省略時は設定から取得）
        
        Returns:
            オーダーブック情報
        """
        if symbol is None:
            symbol = self.trading_config.get('symbol', 'BTC_JPY')
        
        params = {'symbol': symbol}
        
        try:
            data = await self._request('GET', '/v1/orderbooks', params)
            
            if not data:
                return {}
            
            # 必要な情報を抽出
            orderbook = {
                'symbol': symbol,
                'asks': [[float(ask['price']), float(ask['size'])] for ask in data['asks']],
                'bids': [[float(bid['price']), float(bid['size'])] for bid in data['bids']],
                'timestamp': datetime.now(timezone.utc)
            }
            
            # データを検証
            if self.validator.validate_orderbook(orderbook):
                return orderbook
            else:
                self.logger.error("オーダーブックデータの検証に失敗しました")
                return {}
                
        except Exception as e:
            self.logger.error(f"オーダーブック情報の取得に失敗しました: {e}")
            return {}
    
    async def fetch_balance(self) -> Dict[str, Any]:
        """
        口座残高を取得する
        
        Returns:
            残高情報
        """
        try:
            data = await self._request('GET', '/v1/account/assets', is_private=True)
            
            if not data:
                return {}
            
            # 残高情報を整形
            balance = {}
            for asset in data:
                symbol = asset['symbol']
                balance[symbol] = {
                    'amount': float(asset['amount']),
                    'available': float(asset['available']),
                    'conversion_rate': float(asset['conversionRate'])
                }
            
            return balance
            
        except Exception as e:
            self.logger.error(f"残高情報の取得に失敗しました: {e}")
            return {}
    
    async def fetch_positions(self) -> List[Dict[str, Any]]:
        """
        ポジション情報を取得する
        
        Returns:
            ポジション情報リスト
        """
        try:
            data = await self._request('GET', '/v1/openPositions', is_private=True)
            
            if not data or 'list' not in data:
                return []
            
            # ポジション情報を整形
            positions = []
            for pos in data['list']:
                position = {
                    'position_id': pos['positionId'],
                    'symbol': pos['symbol'],
                    'side': pos['side'],
                    'size': float(pos['size']),
                    'order_quantity': float(pos['orderdSize']),
                    'price': float(pos['price']),
                    'loss_gain': float(pos['lossGain']),
                    'leverage': float(pos['leverage']),
                    'timestamp': pd.to_datetime(pos['timestamp'])
                }
                positions.append(position)
            
            return positions
            
        except Exception as e:
            self.logger.error(f"ポジション情報の取得に失敗しました: {e}")
            return []
