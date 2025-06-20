"""
GMOコイン APIクライアント - 本番環境用

実際のAPIデータを取得するためのクライアント
"""

import os
import hmac
import hashlib
import time
import json
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from .logger import get_logger

class GMOCoinClient:
    """GMOコイン APIクライアント"""
    PRIVATE_BASE_URL = 'https://api.coin.z.com/private'
    PUBLIC_BASE_URL = 'https://api.coin.z.com/public'
    
    def __init__(self):
        self.api_key = os.getenv('GMO_API_KEY')
        self.api_secret = os.getenv('GMO_API_SECRET')
        self.logger = get_logger()
        
        if not self.api_key or not self.api_secret:
            raise ValueError("APIキーが設定されていません。.envファイルを確認してください。")
        
        self.api_key = self.api_key.strip()
        self.api_secret = self.api_secret.strip()
    
    def _create_sign(self, text: str) -> str:
        """署名を作成"""
        return hmac.new(
            bytes(self.api_secret, 'utf-8'),
            bytes(text, 'utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _request(self, method: str, base_url: str, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """APIリクエストを送信する内部メソッド"""
        url = f"{base_url}{path}"
        headers = {}
        
        # Private APIの場合のみ署名を生成
        if base_url == self.PRIVATE_BASE_URL:
            timestamp = str(int(time.time() * 1000))
            body_for_sign = ''
            
            if method == 'POST' and params:
                body_for_sign = json.dumps(params, separators=(',', ':'))

            text_for_sign = timestamp + method + path + body_for_sign
            sign = self._create_sign(text_for_sign)

            headers = {
                'API-KEY': self.api_key,
                'API-TIMESTAMP': timestamp,
                'API-SIGN': sign
            }
            self.logger.debug(f"Signature text: {text_for_sign}")

        # GETメソッドのパラメータをURLに追加
        if method == 'GET' and params:
            query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
            url += '?' + query_string
        
        self.logger.debug(f"Request URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                if params:
                    headers['Content-Type'] = 'application/json'
                response = requests.post(url, headers=headers, json=params, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            result = response.json()
            self.logger.debug(f"Response: {result}")
            return result
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"APIリクエストエラー: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    self.logger.error(f"Error detail: {error_detail}")
                except:
                    self.logger.error(f"Response text: {e.response.text}")
            return {"status": 1, "messages": [{"message_string": str(e)}]}
    
    # --- Public API ---
    def get_ticker(self, symbol: str = 'BTC_JPY') -> Dict[str, Any]:
        """最新のティッカー情報を取得"""
        result = self._request('GET', self.PUBLIC_BASE_URL, '/v1/ticker', {'symbol': symbol})
        if result.get('status') == 0:
            data = result.get('data', [{}])[0]
            return {
                'symbol': data.get('symbol'),
                'last': float(data.get('last', 0)),
                'bid': float(data.get('bid', 0)),
                'ask': float(data.get('ask', 0)),
                'high': float(data.get('high', 0)),
                'low': float(data.get('low', 0)),
                'volume': float(data.get('volume', 0)),
                'timestamp': data.get('timestamp')
            }
        else:
            return {}

    # --- Private API ---
    def get_account_balance(self) -> Dict[str, Any]:
        """口座残高を取得"""
        result = self._request('GET', self.PRIVATE_BASE_URL, '/v1/account/assets')
        if result.get('status') == 0:
            balance_data = {'total_jpy': 0, 'assets': [], 'positions': []}
            for asset in result.get('data', []):
                amount = float(asset.get('amount', 0))
                available = float(asset.get('available', 0))
                symbol = asset.get('symbol')
                jpy_value = amount if symbol == 'JPY' else 0
                balance_data['total_jpy'] += jpy_value
                balance_data['assets'].append({'symbol': symbol, 'amount': amount, 'available': available, 'jpy_value': jpy_value})
            return balance_data
        else:
            error_msg = result.get('messages', [{}])[0].get('message_string', 'Unknown error')
            self.logger.error(f"残高取得エラー: {error_msg}")
            return {'total_jpy': 0, 'assets': [], 'positions': [], 'error': error_msg}
    
    def get_positions(self, symbol: str = 'BTC') -> List[Dict[str, Any]]:
        """建玉一覧を取得"""
        result = self._request('GET', self.PRIVATE_BASE_URL, '/v1/openPositions', {'symbol': symbol})
        if result.get('status') == 0:
            positions = []
            for pos in result.get('data', {}).get('list', []):
                positions.append({
                    'symbol': pos.get('symbol'), 'side': pos.get('side'),
                    'size': float(pos.get('size', 0)), 'price': float(pos.get('price', 0)),
                    'lossGain': float(pos.get('lossGain', 0)), 'timestamp': pos.get('timestamp')
                })
            return positions
        else:
            return []
    
    def get_latest_executions(self, symbol: str = 'BTC', count: int = 100) -> List[Dict[str, Any]]:
        """約定履歴を取得"""
        params = {'symbol': symbol, 'count': str(count)}
        result = self._request('GET', self.PRIVATE_BASE_URL, '/v1/latestExecutions', params)
        if result.get('status') == 0:
            trades = []
            for trade in result.get('data', {}).get('list', []):
                trades.append({
                    'executionId': trade.get('executionId'), 'orderId': trade.get('orderId'),
                    'symbol': trade.get('symbol'), 'side': trade.get('side'),
                    'settleType': trade.get('settleType'), 'size': float(trade.get('size', 0)),
                    'price': float(trade.get('price', 0)), 'lossGain': float(trade.get('lossGain', 0)),
                    'fee': float(trade.get('fee', 0)), 'timestamp': trade.get('timestamp')
                })
            return trades
        else:
            return []
    
    def get_trade_history(self, symbol: str = 'BTC_JPY', count: int = 100) -> List[Dict[str, Any]]:
        """取引履歴を取得（約定履歴のラッパー）"""
        if symbol.endswith('_JPY'):
            symbol = symbol[:-4]
        return self.get_latest_executions(symbol=symbol, count=count)
    
    def calculate_performance_metrics(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not trades:
            return {}
        return {"message": "パフォーマンス計算は未実装です"}
