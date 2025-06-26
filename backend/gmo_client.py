"""
GMOコイン APIクライアント - 本番環境用（リファクタリング版）

実際のAPIデータを取得するためのクライアント
"""

import os
import hmac
import hashlib
import time
import json
import requests
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone, timedelta
from .logger import get_logger
from .utils import AssetHistoryDB
from .config_manager import get_config_manager
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from .risk_manager import RiskManager

class APIError(Exception):
    """API関連のエラー"""
    pass

class NetworkError(Exception):
    """ネットワーク関連のエラー"""
    pass

class GMOCoinClient:
    """GMOコイン APIクライアント（リファクタリング版）"""
    
    # === 定数定義 ===
    PRIVATE_BASE_URL = 'https://api.coin.z.com/private'
    PUBLIC_BASE_URL = 'https://api.coin.z.com/public'
    MIN_REQUEST_INTERVAL = 0.06  # GMO 公式は 20 req/s (0.05s) → 余裕を持って 0.06s
    DEFAULT_TIMEOUT = 10
    MAX_RETRIES = 3
    
    def __init__(self):
        """クライアント初期化"""
        self.config = get_config_manager()
        self.logger = get_logger()
        
        # API認証設定
        self._setup_api_credentials()
        
        # システムコンポーネント初期化
        self._setup_components()
        
        # HTTP設定
        self._setup_session()
        
        # レート制限設定
        self.last_request_time = 0
        
        self.logger.info(f"GMOクライアント初期化完了 - ベースURL: {self.PRIVATE_BASE_URL}")
    
    def _setup_api_credentials(self):
        """API認証情報の設定"""
        self.api_key = os.getenv('GMO_API_KEY')
        self.api_secret = os.getenv('GMO_API_SECRET')
        
        if not self.api_key or not self.api_secret:
            raise ValueError("APIキーが設定されていません。.envファイルを確認してください。")
        
        self.api_key = self.api_key.strip()
        self.api_secret = self.api_secret.strip()
    
    def _setup_components(self):
        """システムコンポーネントの初期化"""
        # 資産履歴データベース
        try:
            self.asset_history_db = AssetHistoryDB()
            self.logger.info("資産履歴データベースの初期化に成功しました")
        except Exception as e:
            self.logger.error(f"資産履歴データベースの初期化に失敗しました: {e}")
            self.asset_history_db = None
        
        # リスク管理システム
        self.risk_manager = RiskManager()
        
        # 緊急停止フラグ
        self.emergency_stop = False
    
    def _setup_session(self):
        """HTTPセッションの設定"""
        self.session = requests.Session()
        
        try:
            retry_strategy = Retry(
                total=self.MAX_RETRIES,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "POST"],
                backoff_factor=1
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
        except Exception as e:
            self.logger.warning(f"HTTP再試行設定に失敗しました（標準設定を使用）: {e}")
    
    def _create_sign(self, text: str) -> str:
        """署名を作成"""
        return hmac.new(
            bytes(self.api_secret, 'utf-8'),
            bytes(text, 'utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _handle_rate_limit(self):
        """レート制限の処理"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.MIN_REQUEST_INTERVAL:
            time.sleep(self.MIN_REQUEST_INTERVAL - time_since_last)
    
    def _create_headers(self, method: str, path: str, params: Optional[Dict] = None) -> Dict[str, str]:
        """Private API用のヘッダーを作成"""
        timestamp = str(int(time.time() * 1000))
        body_for_sign = ''
        
        if method == 'POST' and params:
            body_for_sign = json.dumps(params, separators=(',', ':'))

        text_for_sign = timestamp + method + path + body_for_sign
        sign = self._create_sign(text_for_sign)

        return {
            'API-KEY': self.api_key,
            'API-TIMESTAMP': timestamp,
            'API-SIGN': sign
        }
    
    def _execute_request(self, method: str, url: str, headers: Dict[str, str], params: Optional[Dict] = None) -> requests.Response:
        """HTTPリクエストの実行"""
        if method == 'GET':
            if params:
                query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
                url += '?' + query_string
            return self.session.get(url, headers=headers, timeout=self.DEFAULT_TIMEOUT)
        elif method == 'POST':
            return self.session.post(url, headers=headers, json=params, timeout=self.DEFAULT_TIMEOUT)
        else:
            raise ValueError(f"Unsupported method: {method}")
    
    def _request(self, method: str, base_url: str, path: str, params: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """統一化されたAPIリクエストメソッド"""
        try:
            # レート制限
            self._handle_rate_limit()
            
            url = f"{base_url}{path}"
            headers = {}
            
            # Private APIの場合のみ署名を生成
            if base_url == self.PRIVATE_BASE_URL:
                headers = self._create_headers(method, path, params)
                self.logger.debug(f"Private API request: {path}")
            
            self.logger.debug(f"Request URL: {url}")
            
            # リクエスト実行
            response = self._execute_request(method, url, headers, params)
            response.raise_for_status()
            
            self.last_request_time = time.time()
            result = response.json()
            self.logger.debug(f"Response: {result}")
            return result

        except requests.exceptions.ConnectionError as e:
            self.logger.warning(f"ネットワーク接続エラー (一時的な可能性): {path} - {str(e)}")
            raise NetworkError(f"接続エラー: {str(e)}")
        except requests.exceptions.Timeout as e:
            self.logger.warning(f"APIタイムアウト: {path} - {str(e)}")
            raise NetworkError(f"タイムアウト: {str(e)}")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"APIリクエストエラー: {str(e)}")
            raise APIError(f"リクエストエラー: {str(e)}")
        except Exception as e:
            self.logger.error(f"予期しないエラー: {str(e)}")
            raise APIError(f"予期しないエラー: {str(e)}")
    
    def _safe_api_call(self, method: str, base_url: str, path: str, params: Optional[Dict] = None, default_return: Any = None):
        """安全なAPI呼び出し（エラー時にNoneまたはデフォルト値を返す）"""
        try:
            return self._request(method, base_url, path, params)
        except (NetworkError, APIError) as e:
            self.logger.warning(f"API呼び出し失敗: {path} - {str(e)}")
            return default_return
    
    # === Public API ===
    def get_ticker(self, symbol: str = 'BTC_JPY') -> Dict[str, Any]:
        """最新のティッカー情報を取得"""
        result = self._safe_api_call('GET', self.PUBLIC_BASE_URL, '/v1/ticker', {'symbol': symbol}, {})
        
        if result and result.get('status') == 0:
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
        return {}

    # === Private API ===
    def get_account_balance(self) -> Optional[Dict[str, Any]]:
        """口座残高を取得"""
        try:
            # まず現物口座の資産を取得
            assets_response = self._safe_api_call('GET', self.PRIVATE_BASE_URL, '/v1/account/assets')
            
            if not assets_response or assets_response.get('status') != 0:
                self.logger.warning("現物口座資産取得失敗、証拠金口座を試行")
                # 証拠金口座を試行
                margin_response = self._safe_api_call('GET', self.PRIVATE_BASE_URL, '/v1/account/margin', default_return=None)
                if margin_response and isinstance(margin_response, dict):
                    balance_info = margin_response.get('data', {})
                    if isinstance(balance_info, list) and len(balance_info) > 0:
                        balance_info = balance_info[0]
                    
                    available = float(balance_info.get('availableAmount', 0))
                    margin = float(balance_info.get('margin', 0))
                    profit_loss = float(balance_info.get('profitLoss', 0))
                    total_jpy = available + margin + profit_loss
                    
                    return {
                        'total_jpy': total_jpy,
                        'assets': [{'symbol': 'JPY', 'amount': total_jpy, 'available': available}],
                        'availableAmount': available,
                        'margin': margin,
                        'profitLoss': profit_loss
                    }
                return None
            
            # 現物口座の処理
            balance_data = {'total_jpy': 0, 'assets': [], 'positions': []}
            for asset in assets_response.get('data', []):
                amount = float(asset.get('amount', 0))
                available = float(asset.get('available', 0))
                symbol = asset.get('symbol')
                jpy_value = amount if symbol == 'JPY' else 0
                balance_data['total_jpy'] += jpy_value
                balance_data['assets'].append({
                    'symbol': symbol, 
                    'amount': amount, 
                    'available': available, 
                    'jpy_value': jpy_value
                })
            return balance_data
            
        except Exception as e:
            self.logger.error(f"口座残高取得エラー: {e}")
            return None
    
    def get_account_info(self) -> Dict[str, Any]:
        """
        口座情報を取得（get_account_balanceの拡張版）
        
        Returns:
            口座情報の辞書
        """
        try:
            balance_data = self.get_account_balance()
            if not balance_data:
                self.logger.warning("口座残高データを取得できません")
                return {
                    'total_balance': 0,
                    'available_balance': 0,
                    'margin': 0,
                    'profit_loss': 0,
                    'margin_level': 1.0
                }
            
            # 総残高の計算
            available_amount = balance_data.get('availableAmount', 0)
            margin = balance_data.get('margin', 0)
            profit_loss = balance_data.get('profitLoss', 0)
            
            total_balance = available_amount + margin + profit_loss
            
            # 証拠金維持率の計算（margin > 0の場合のみ）
            margin_level = 1.0
            if margin > 0:
                margin_level = total_balance / margin
            
            return {
                'total_balance': total_balance,
                'available_balance': available_amount,
                'transferable_amount': balance_data.get('transferableAmount', 0),
                'margin': margin,
                'profit_loss': profit_loss,
                'margin_level': margin_level
            }
            
        except Exception as e:
            self.logger.error(f"口座情報取得エラー: {e}")
            return {
                'total_balance': 0,
                'available_balance': 0,
                'margin': 0,
                'profit_loss': 0,
                'margin_level': 1.0
            }
    
    def _normalize_symbol(self, symbol: str) -> str:
        """シンボル名の正規化"""
        if not symbol.endswith('_JPY'):
            symbol += '_JPY'
        return symbol
    
    def get_positions(self, symbol: str = 'BTC_JPY') -> List[Dict[str, Any]]:
        """建玉一覧を取得（証拠金取引のポジション）"""
        symbol = self._normalize_symbol(symbol)
        
        # 正しいエンドポイント：/v1/openPositions
        response = self._safe_api_call('GET', self.PRIVATE_BASE_URL, '/v1/openPositions', {'symbol': symbol}, [])
        
        if not response or response.get('status') != 0:
            self.logger.warning(f"ポジション取得失敗: {response}")
            return []
        
        positions = []
        data = response.get('data', [])
        
        # データが文字列の場合は空リストを返す
        if isinstance(data, str):
            self.logger.warning(f"ポジションデータが文字列形式: {data}")
            return []
        
        # dataが辞書の場合はlistに変換
        if isinstance(data, dict):
            data = [data]
        
        for pos in data:
            # pos自体も辞書型であることを確認
            if isinstance(pos, dict):
                positions.append({
                    'symbol': pos.get('symbol'),
                    'side': pos.get('side'),
                    'size': float(pos.get('size', 0)),
                    'price': float(pos.get('price', 0)),
                    'loss_gain': float(pos.get('lossGain', 0)),
                    'timestamp': pos.get('timestamp')
                })
            else:
                self.logger.warning(f"ポジションアイテムが辞書型ではありません: {type(pos)} - {pos}")
        
        return positions

    def get_latest_executions(self, symbol: str = 'BTC_JPY', count: int = 100) -> List[Dict[str, Any]]:
        """約定履歴を取得"""
        try:
            # symbol は _normalize_symbol せず BTC_JPY / ETH_JPY 形式で渡す
            params = {
                'symbol': symbol,
                'count': str(min(count, 100))
            }
            
            result = self._safe_api_call('GET',
                                         self.PRIVATE_BASE_URL,
                                         '/v1/latestExecutions',
                                         params, {})
            
            # latestExecutions しか存在しないのでフォールバックを削除
            if not result or result.get('status') != 0:
                err = result.get('messages', [{}])[0].get('message_string', 'unknown') if result else 'no response'
                self.logger.warning(f"latestExecutions 取得失敗: {err}")
                return []
            
            trades = []
            data = result.get('data', [])
            
            # データが文字列の場合は空リストを返す
            if isinstance(data, str):
                self.logger.warning(f"取引履歴データが文字列形式: {data}")
                return []
            
            # データが辞書の場合はリストに変換
            if isinstance(data, dict):
                data = [data]
            
            for trade in data:
                # trade自体も辞書型であることを確認
                if isinstance(trade, dict):
                    trades.append({
                        'executionId': trade.get('executionId'),
                        'orderId': trade.get('orderId'),
                        'symbol': trade.get('symbol'),
                        'side': trade.get('side'),
                        'settleType': trade.get('settleType'),
                        'size': float(trade.get('size', 0)),
                        'price': float(trade.get('price', 0)),
                        'lossGain': float(trade.get('lossGain', 0)),
                        'fee': float(trade.get('fee', 0)),
                        'timestamp': trade.get('timestamp')
                    })
                else:
                    self.logger.warning(f"取引履歴アイテムが辞書型ではありません: {type(trade)} - {trade}")
            
            self.logger.info(f"取得した取引履歴数: {len(trades)}")
            return trades
            
        except Exception as e:
            self.logger.error(f"取引履歴取得エラー: {e}")
            return []
    
    def get_trade_history(self, symbol: str = 'BTC_JPY', count: int = 100) -> List[Dict[str, Any]]:
        """取引履歴を取得（約定履歴のラッパー）"""
        # symbolはそのまま（BTC_JPY形式）で渡す
        return self.get_latest_executions(symbol=symbol, count=count)
    
    def calculate_performance_metrics(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """取引履歴からパフォーマンス指標を計算"""
        if not trades:
            return {
                'total_pnl': 0,
                'win_rate': 0,
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'total_fees': 0
            }
        
        # 基本統計
        total_trades = len(trades)
        total_pnl = sum(trade.get('lossGain', 0) for trade in trades)
        total_fees = sum(trade.get('fee', 0) for trade in trades)
        
        # 勝敗計算
        winning_trades = len([t for t in trades if t.get('lossGain', 0) > 0])
        losing_trades = len([t for t in trades if t.get('lossGain', 0) < 0])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        self.logger.info(f"パフォーマンス計算完了: 総取引{total_trades}, 総損益{total_pnl}, 勝率{win_rate:.1f}%")
        
        return {
            'total_pnl': total_pnl,
            'win_rate': win_rate,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'total_fees': total_fees
        }

    def get_spot_holdings(self) -> List[Dict[str, Any]]:
        """現物保有資産をポジション形式で取得"""
        balance_data = self.get_account_balance()
        if not balance_data:
            return []
        
        holdings = []
        for asset in balance_data.get('assets', []):
            if asset['symbol'] != 'JPY' and asset['amount'] > 0:
                # 現在価格を取得
                ticker = self.get_ticker(f"{asset['symbol']}_JPY")
                current_price = ticker.get('last', 0) if ticker else 0
                
                holdings.append({
                    'symbol': f"{asset['symbol']}_JPY",
                    'side': 'LONG',  # 現物は常にLONG
                    'size': asset['amount'],
                    'price': current_price,  # 現在価格（取得価格不明のため）
                    'lossGain': 0,  # 取得価格不明のため0
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'type': 'SPOT'  # 現物を示すフラグ
                })
        
        self.logger.info(f"現物保有数: {len(holdings)}")
        return holdings

    def get_all_positions(self) -> List[Dict[str, Any]]:
        """証拠金取引のポジション + 現物保有を統合取得"""
        # 証拠金取引のポジション
        margin_positions = self.get_positions()
        
        # 現物保有
        spot_holdings = self.get_spot_holdings()
        
        # 統合
        all_positions = margin_positions + spot_holdings
        self.logger.info(f"全ポジション数: {len(all_positions)} (証拠金: {len(margin_positions)}, 現物: {len(spot_holdings)})")
        
        return all_positions

    def get_today_trade_count(self) -> int:
        """当日の取引回数を取得"""
        try:
            # 今日の日付
            today = datetime.now().strftime('%Y%m%d')
            
            # 当日の約定履歴を取得（symbolパラメータを追加）
            result = self._safe_api_call('GET', self.PRIVATE_BASE_URL, '/v1/latestExecutions', {
                'symbol': 'BTC_JPY',  # デフォルトシンボル
                'count': '100'  # 最大100件取得
            })
            
            if result and result.get('status') == 0:
                trades = result.get('data', [])
                today_trades = 0
                
                # データが文字列の場合はスキップ
                if isinstance(trades, str):
                    return 0
                
                for trade in trades:
                    if not isinstance(trade, dict):
                        continue
                    trade_timestamp = trade.get('timestamp')
                    if trade_timestamp:
                        # タイムスタンプから日付を抽出
                        trade_date = datetime.fromtimestamp(int(trade_timestamp) / 1000).strftime('%Y%m%d')
                        if trade_date == today:
                            today_trades += 1
                
                self.logger.info(f"当日取引回数: {today_trades}")
                return today_trades
            
            return 0
        except Exception as e:
            self.logger.error(f"当日取引回数取得エラー: {e}")
            return 0

    def get_api_rate_status(self) -> Dict[str, Any]:
        """APIレート制限の使用状況を取得（概算）"""
        try:
            # GMOコインは明示的なレート制限情報を返さないので
            # 最近のAPI呼び出し回数を追跡する簡易実装
            if not hasattr(self, '_api_call_timestamps'):
                self._api_call_timestamps = []
            
            # 現在時刻
            now = datetime.now().timestamp()
            
            # 過去1秒間のAPI呼び出し回数をカウント
            recent_calls = [ts for ts in self._api_call_timestamps if now - ts <= 1.0]
            
            # GMOコイン Tier1制限: 20req/s
            max_calls_per_second = 20
            usage_percentage = min((len(recent_calls) / max_calls_per_second) * 100, 100)
            
            return {
                'current_calls': len(recent_calls),
                'max_calls': max_calls_per_second,
                'usage_percentage': usage_percentage,
                'status': 'normal' if usage_percentage < 80 else 'warning' if usage_percentage < 95 else 'critical'
            }
        except Exception as e:
            self.logger.error(f"APIレート状況取得エラー: {e}")
            return {
                'current_calls': 0,
                'max_calls': 20,
                'usage_percentage': 0,
                'status': 'unknown'
            }

    def get_balance_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """残高履歴を取得（実装制限により簡易版）"""
        try:
            # GMOコインAPIには残高履歴APIがないため
            # 現在の残高から過去の推定値を計算（取引履歴ベース）
            current_balance = self.get_account_balance()
            if not current_balance or isinstance(current_balance, str):
                return []
            
            current_total = current_balance.get('total_jpy', 0)
            
            # 取引履歴から損益を逆算
            trades = self.get_latest_executions(count=100)
            
            history = []
            running_balance = current_total
            
            # 日付ごとにグループ化して計算
            from collections import defaultdict
            daily_pnl = defaultdict(float)
            
            for trade in trades:
                if trade.get('timestamp'):
                    trade_date = datetime.fromtimestamp(int(trade.get('timestamp')) / 1000).date()
                    # 簡易的な損益計算（手数料を考慮）
                    fee = trade.get('fee', 0)
                    daily_pnl[trade_date] -= fee
            
            # 過去N日分の履歴を生成
            for i in range(days):
                date = datetime.now().date() - timedelta(days=i)
                pnl = daily_pnl.get(date, 0)
                running_balance -= pnl
                
                history.append({
                    'date': date.isoformat(),
                    'balance': max(running_balance, 0),  # 負の値を避ける
                    'pnl': pnl
                })
            
            # 日付順にソート
            history.reverse()
            self.logger.info(f"残高履歴を{len(history)}日分生成")
            return history
            
        except Exception as e:
            self.logger.error(f"残高履歴取得エラー: {e}")
            return []

    # --- 注文管理機能 ---
    def get_active_orders(self, symbol: str = 'BTC_JPY') -> List[Dict[str, Any]]:
        """有効注文一覧を取得"""
        try:
            result = self._safe_api_call('GET', self.PRIVATE_BASE_URL, '/v1/activeOrders', {'symbol': symbol}, {})
            
            if result and result.get('status') == 0:
                orders = []
                data = result.get('data', [])
                
                # データが文字列の場合は空リストを返す
                if isinstance(data, str):
                    self.logger.warning(f"有効注文データが文字列形式: {data}")
                    return []
                
                for order in data:
                    # order自体も辞書型であることを確認
                    if isinstance(order, dict):
                        order_data = {
                            'orderId': order.get('orderId'),
                            'symbol': order.get('symbol'),
                            'side': order.get('side'),
                            'orderType': order.get('orderType'),
                            'size': float(order.get('size', 0)),
                            'price': float(order.get('price', 0)),
                            'timeInForce': order.get('timeInForce'),
                            'status': order.get('status'),
                            'timestamp': order.get('timestamp')
                        }
                        orders.append(order_data)
                    else:
                        self.logger.warning(f"注文アイテムが辞書型ではありません: {type(order)} - {order}")
                
                self.logger.info(f"取得した有効注文数: {len(orders)}")
                return orders
            else:
                if result:
                    error_msg = result.get('messages', [{}])[0].get('message_string', 'Unknown error')
                    self.logger.warning(f"有効注文取得エラー: {error_msg}")
                return []
                
        except Exception as e:
            self.logger.error(f"有効注文取得エラー: {e}")
            return []

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """注文をキャンセル"""
        try:
            result = self._safe_api_call('POST', self.PRIVATE_BASE_URL, '/v1/cancelOrder', {
                'orderId': order_id
            }, {})
            
            if result and result.get('status') == 0:
                self.logger.info(f"注文キャンセル成功: {order_id}")
                return {'success': True, 'orderId': order_id}
            else:
                error_msg = 'API呼び出し失敗'
                if result:
                    error_msg = result.get('messages', [{}])[0].get('message_string', 'Unknown error')
                self.logger.error(f"注文キャンセル失敗: {error_msg}")
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            self.logger.error(f"注文キャンセルエラー: {e}")
            return {'success': False, 'error': str(e)}

    def place_order(self, side: str, size: float, order_type: str = 'MARKET', 
                   price: float = None, symbol: str = 'BTC_JPY') -> Dict[str, Any]:
        """注文を発注"""
        try:
            order_data = {
                'symbol': symbol,
                'side': side,  # BUY or SELL
                'executionType': order_type,  # MARKET, LIMIT, STOP
                'size': str(size)
            }
            
            if order_type == 'LIMIT' and price:
                order_data['price'] = str(price)
            
            result = self._safe_api_call('POST', self.PRIVATE_BASE_URL, '/v1/order', order_data, {})
            
            if result and result.get('status') == 0:
                order_id = result.get('data')
                self.logger.info(f"注文発注成功: {order_id}")
                return {'success': True, 'orderId': order_id, 'side': side, 'size': size}
            else:
                error_msg = 'API呼び出し失敗'
                if result:
                    error_msg = result.get('messages', [{}])[0].get('message_string', 'Unknown error')
                self.logger.error(f"注文発注失敗: {error_msg}")
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            self.logger.error(f"注文発注エラー: {e}")
            return {'success': False, 'error': str(e)}

    def cancel_all_orders(self, symbol: str = 'BTC_JPY') -> Dict[str, Any]:
        """全注文をキャンセル（パニック機能）"""
        try:
            # 有効注文一覧を取得
            active_orders = self.get_active_orders(symbol)
            
            cancelled_orders = []
            failed_orders = []
            
            for order in active_orders:
                result = self.cancel_order(order['orderId'])
                if result['success']:
                    cancelled_orders.append(order['orderId'])
                else:
                    failed_orders.append({'orderId': order['orderId'], 'error': result['error']})
            
            self.logger.info(f"全注文キャンセル完了: 成功{len(cancelled_orders)}, 失敗{len(failed_orders)}")
            
            return {
                'success': len(failed_orders) == 0,
                'cancelled_count': len(cancelled_orders),
                'failed_count': len(failed_orders),
                'cancelled_orders': cancelled_orders,
                'failed_orders': failed_orders
            }
            
        except Exception as e:
            self.logger.error(f"全注文キャンセルエラー: {e}")
            return {'success': False, 'error': str(e)}

    def close_position(self, symbol: str = 'BTC_JPY', size: float = None) -> Dict[str, Any]:
        """ポジションを成行決済"""
        try:
            # 現在のポジションを確認
            positions = self.get_positions(symbol)
            if not positions:
                return {'success': False, 'error': 'ポジションが見つかりません'}
            
            position = positions[0]  # 最初のポジション
            position_side = position['side']
            position_size = position['size']
            
            # 決済サイズ（指定がなければ全決済）
            close_size = size if size else position_size
            
            # 反対売買
            close_side = 'SELL' if position_side == 'BUY' else 'BUY'
            
            # 成行注文で決済
            result = self.place_order(
                side=close_side,
                size=close_size,
                order_type='MARKET',
                symbol=symbol
            )
            
            if result['success']:
                self.logger.info(f"ポジション決済成功: {symbol} {close_side} {close_size}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"ポジション決済エラー: {e}")
            return {'success': False, 'error': str(e)}

    def calculate_liquidation_price(self, symbol: str = 'BTC_JPY') -> Dict[str, Any]:
        """ロスカット価格を計算（簡易版）"""
        try:
            # ポジション情報取得
            positions = self.get_positions(symbol)
            if not positions:
                self.logger.info("ポジションが存在しないため、ロスカット価格計算をスキップ")
                return {}
            
            # 口座情報取得
            balance = self.get_account_balance()
            if not balance or isinstance(balance, str):
                self.logger.warning("口座残高が取得できないため、ロスカット価格計算をスキップ")
                return {}
            
            available_jpy = balance.get('total_jpy', 0)
            if available_jpy <= 0:
                self.logger.warning("利用可能残高が0以下のため、ロスカット価格計算をスキップ")
                return {}
            
            liquidation_info = {}
            
            for position in positions:
                try:
                    position_side = position.get('side', '')
                    entry_price = float(position.get('price', 0))
                    position_size = float(position.get('size', 0))
                    
                    # ゼロ除算を防ぐチェック
                    if entry_price <= 0 or position_size <= 0:
                        self.logger.warning(f"無効なポジションデータ: price={entry_price}, size={position_size}")
                        continue
                    
                    # 簡易ロスカット計算（証拠金維持率75%として）
                    required_margin = entry_price * position_size * 0.04  # レバレッジ25倍の場合
                    liquidation_margin_rate = 0.75  # 75%
                    
                    if required_margin <= 0:
                        self.logger.warning(f"必要証拠金が0以下: {required_margin}")
                        continue
                    
                    # ロスカット価格計算（ゼロ除算を防止）
                    margin_ratio = (available_jpy * liquidation_margin_rate) / (entry_price * position_size)
                    
                    if position_side == 'BUY':
                        # ロング：価格下落でロスカット
                        liquidation_price = entry_price * (1 - margin_ratio)
                    else:
                        # ショート：価格上昇でロスカット
                        liquidation_price = entry_price * (1 + margin_ratio)
                    
                    # 現在の証拠金維持率計算
                    current_margin_rate = (available_jpy / required_margin) * 100 if required_margin > 0 else 0
                    
                    liquidation_info[position.get('symbol', symbol)] = {
                        'liquidation_price': max(liquidation_price, 0),
                        'position_side': position_side,
                        'entry_price': entry_price,
                        'position_size': position_size,
                        'current_margin_rate': current_margin_rate,
                        'required_margin': required_margin
                    }
                    
                except Exception as pos_error:
                    self.logger.warning(f"ポジション個別計算エラー: {pos_error}")
                    continue
            
            self.logger.info(f"ロスカット価格計算完了: {len(liquidation_info)}ポジション")
            return liquidation_info
            
        except Exception as e:
            self.logger.error(f"ロスカット価格計算エラー: {e}")
            return {}
    
    # --- 資産履歴管理機能 ---
    def calculate_total_assets(self) -> Dict[str, Any]:
        """
        総資産を計算（修正版）
        
        Returns:
            総資産情報
        """
        try:
            # 残高情報を取得
            balance = self.get_account_balance()
            if not balance or isinstance(balance, str):
                self.logger.warning("残高情報の取得に失敗しました")
                return {'error': '残高情報の取得に失敗しました', 'total_assets': 0}
            
            # 基本残高（JPY）
            jpy_balance = balance.get('total_jpy', 0)
            
            # 現物保有の評価額を計算
            spot_value = 0
            assets = balance.get('assets', [])
            asset_breakdown = {}
            
            for asset in assets:
                if isinstance(asset, dict) and asset.get('symbol') != 'JPY' and asset.get('amount', 0) > 0:
                    try:
                        # 現在価格を取得
                        ticker = self.get_ticker(f"{asset['symbol']}_JPY")
                        if ticker and ticker.get('last', 0) > 0:
                            current_price = float(ticker.get('last', 0))
                            amount = float(asset.get('amount', 0))
                            value = current_price * amount
                            spot_value += value
                            asset_breakdown[asset['symbol']] = {
                                'amount': amount,
                                'price': current_price,
                                'value': value
                            }
                        else:
                            self.logger.warning(f"価格取得失敗: {asset['symbol']}")
                    except Exception as asset_error:
                        self.logger.warning(f"資産評価エラー ({asset.get('symbol', 'unknown')}): {asset_error}")
                        continue
            
            # 証拠金取引の評価損益を計算
            margin_pnl = 0
            try:
                positions = self.get_all_positions()
                margin_positions = [p for p in positions if p.get('type') != 'SPOT']
                for pos in margin_positions:
                    if isinstance(pos, dict):
                        margin_pnl += float(pos.get('loss_gain', 0))
            except Exception as position_error:
                self.logger.warning(f"ポジション評価エラー: {position_error}")
            
            # 総資産 = JPY残高 + 現物評価額 + 証拠金損益
            total_assets = jpy_balance + spot_value + margin_pnl
            
            result = {
                'total_assets': total_assets,
                'jpy_balance': jpy_balance,
                'spot_value': spot_value,
                'margin_pnl': margin_pnl,
                'asset_breakdown': asset_breakdown
            }
            
            self.logger.info(f"総資産計算完了: ¥{total_assets:,.0f} (JPY: ¥{jpy_balance:,.0f}, 現物: ¥{spot_value:,.0f}, 証拠金損益: ¥{margin_pnl:,.0f})")
            return result
            
        except Exception as e:
            self.logger.error(f"総資産計算エラー: {e}")
            return {'error': str(e), 'total_assets': 0}
    
    def save_daily_assets(self, notes: str = None) -> bool:
        """
        今日の総資産をデータベースに保存
        
        Args:
            notes: 備考
            
        Returns:
            保存成功フラグ
        """
        try:
            # AssetHistoryDBが初期化されていない場合
            if self.asset_history_db is None:
                self.logger.warning("資産履歴データベースが初期化されていないため、保存をスキップします")
                return False
            
            # 総資産を計算
            asset_data = self.calculate_total_assets()
            
            if not asset_data or 'error' in asset_data:
                error_msg = asset_data.get('error', '不明なエラー') if asset_data else '総資産計算に失敗しました'
                self.logger.error(f"総資産保存失敗: {error_msg}")
                return False
            
            # データベースに保存
            success = self.asset_history_db.save_daily_assets(
                total_assets=asset_data['total_assets'],
                jpy_balance=asset_data['jpy_balance'],
                spot_value=asset_data['spot_value'],
                margin_pnl=asset_data['margin_pnl'],
                asset_breakdown=asset_data['asset_breakdown'],
                notes=notes
            )
            
            if success:
                self.logger.info(f"総資産保存成功: ¥{asset_data['total_assets']:,.0f}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"総資産保存エラー: {e}")
            return False
    
    def get_asset_history_data(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        資産履歴を取得
        
        Args:
            days: 取得日数
            
        Returns:
            資産履歴リスト
        """
        try:
            # AssetHistoryDBが初期化されていない場合
            if self.asset_history_db is None:
                self.logger.warning("資産履歴データベースが初期化されていないため、空のリストを返します")
                return []
            
            df = self.asset_history_db.get_asset_history(days)
            
            if df.empty:
                return []
            
            # DataFrameを辞書リストに変換
            history = []
            for _, row in df.iterrows():
                history.append({
                    'date': row['date'].isoformat(),
                    'timestamp': row['timestamp'].isoformat(),
                    'total_assets': row['total_assets'],
                    'jpy_balance': row['jpy_balance'],
                    'spot_value': row['spot_value'],
                    'margin_pnl': row['margin_pnl'],
                    'asset_breakdown': row['asset_breakdown']
                })
            
            return history
            
        except Exception as e:
            self.logger.error(f"資産履歴取得エラー: {e}")
            return []

    def check_risk_before_trade(self, signal: 'Signal', symbol: str = 'BTC_JPY') -> Tuple[bool, str, Dict[str, Any]]:
        """
        取引前のリスクチェック
        
        Args:
            signal: 取引シグナル
            symbol: 取引銘柄
            
        Returns:
            (取引可能か, 理由, リスク情報)のタプル
        """
        try:
            # 緊急停止チェック
            if self.emergency_stop:
                return False, "緊急停止中です", {}
            
            # 口座情報取得
            account_info = self.get_account_info()
            if not account_info:
                return False, "口座情報が取得できません", {}
            
            # 現在のポジション取得
            positions = self.get_positions()
            
            # リスク制限チェック
            can_trade, risk_reason = self.risk_manager.check_risk_limits(account_info, positions)
            
            if not can_trade:
                return False, risk_reason, {}
            
            # 現在価格取得
            ticker = self.get_ticker(symbol)
            if not ticker:
                return False, "価格情報が取得できません", {}
            
            current_price = float(ticker.get('last', 0))
            if current_price <= 0:
                return False, "無効な価格です", {}
            
            # ポジションサイズ計算
            total_balance = account_info.get('total_balance', 0)
            position_size = self.risk_manager.calculate_position_size(
                signal, total_balance, current_price
            )
            
            if position_size <= 0:
                return False, "計算されたポジションサイズが無効です", {}
            
            # ストップロス・テイクプロフィット計算
            stop_loss_price = self.risk_manager.calculate_stop_loss(signal, current_price)
            take_profit_price = self.risk_manager.calculate_take_profit(signal, current_price, stop_loss_price)
            
            risk_info = {
                'position_size': position_size,
                'current_price': current_price,
                'stop_loss_price': stop_loss_price,
                'take_profit_price': take_profit_price,
                'risk_amount': total_balance * self.risk_manager.risk_config.get('position_sizing', {}).get('risk_per_trade', 0.02),
                'account_balance': total_balance,
                'current_positions': len(positions),
                'max_positions': self.risk_manager.risk_config.get('max_open_positions', 3)
            }
            
            return True, "リスクチェック通過", risk_info
            
        except Exception as e:
            self.logger.error(f"リスクチェックエラー: {e}")
            return False, f"リスクチェックエラー: {str(e)}", {}

    def execute_trade_with_risk_management(self, signal: 'Signal', symbol: str = 'BTC_JPY') -> Dict[str, Any]:
        """
        リスク管理付き取引実行
        
        Args:
            signal: 取引シグナル
            symbol: 取引銘柄
            
        Returns:
            取引結果
        """
        try:
            # リスクチェック
            can_trade, reason, risk_info = self.check_risk_before_trade(signal, symbol)
            
            if not can_trade:
                return {
                    'success': False,
                    'error': reason,
                    'risk_info': risk_info
                }
            
            # 注文データ作成
            side = 'BUY' if signal.value in ['BUY'] else 'SELL'
            position_size = risk_info['position_size']
            
            order_data = {
                'symbol': symbol,
                'side': side,
                'executionType': 'MARKET',  # 成行注文
                'size': str(position_size)
            }
            
            # 注文実行
            order_result = self.place_order(order_data)
            
            if order_result.get('success'):
                # 取引履歴を記録
                trade_record = {
                    'timestamp': datetime.now().isoformat(),
                    'symbol': symbol,
                    'side': side,
                    'size': position_size,
                    'price': risk_info['current_price'],
                    'signal': signal.value,
                    'stop_loss': risk_info.get('stop_loss_price'),
                    'take_profit': risk_info.get('take_profit_price'),
                    'risk_amount': risk_info.get('risk_amount'),
                    'order_id': order_result.get('order_id')
                }
                
                self.risk_manager.update_trade_history(trade_record)
                
                # ストップロス・テイクプロフィット注文の設定（実装予定）
                if risk_info.get('stop_loss_price'):
                    self._set_stop_loss_order(order_result.get('order_id'), risk_info['stop_loss_price'])
                
                if risk_info.get('take_profit_price'):
                    self._set_take_profit_order(order_result.get('order_id'), risk_info['take_profit_price'])
                
                return {
                    'success': True,
                    'order_result': order_result,
                    'risk_info': risk_info,
                    'trade_record': trade_record
                }
            else:
                return {
                    'success': False,
                    'error': order_result.get('error', '注文に失敗しました'),
                    'risk_info': risk_info
                }
                
        except Exception as e:
            self.logger.error(f"リスク管理付き取引実行エラー: {e}")
            return {
                'success': False,
                'error': f"取引実行エラー: {str(e)}",
                'risk_info': {}
            }

    def _set_stop_loss_order(self, original_order_id: str, stop_loss_price: float) -> Dict[str, Any]:
        """
        ストップロス注文設定（将来実装）
        
        Args:
            original_order_id: 元の注文ID
            stop_loss_price: ストップロス価格
            
        Returns:
            設定結果
        """
        # 実装予定：GMOコインのストップロス注文API
        self.logger.info(f"ストップロス注文設定予定: {original_order_id} @ {stop_loss_price}")
        return {'success': True, 'message': 'ストップロス注文設定予定'}

    def _set_take_profit_order(self, original_order_id: str, take_profit_price: float) -> Dict[str, Any]:
        """
        テイクプロフィット注文設定（将来実装）
        
        Args:
            original_order_id: 元の注文ID
            take_profit_price: テイクプロフィット価格
            
        Returns:
            設定結果
        """
        # 実装予定：GMOコインのテイクプロフィット注文API
        self.logger.info(f"テイクプロフィット注文設定予定: {original_order_id} @ {take_profit_price}")
        return {'success': True, 'message': 'テイクプロフィット注文設定予定'}

    def get_risk_status(self) -> Dict[str, Any]:
        """
        現在のリスク状況を取得
        
        Returns:
            リスク状況
        """
        try:
            # 口座情報とポジション取得
            account_info = self.get_account_info()
            positions = self.get_positions()
            
            # リスクチェック
            can_trade, risk_reason = self.risk_manager.check_risk_limits(account_info, positions)
            
            # ポートフォリオメトリクス
            metrics = self.risk_manager.calculate_portfolio_metrics()
            
            return {
                'can_trade': can_trade,
                'risk_reason': risk_reason,
                'emergency_stop': self.emergency_stop,
                'current_positions': len(positions),
                'max_positions': self.risk_manager.risk_config.get('max_open_positions', 3),
                'daily_trades': self.risk_manager.daily_trades,
                'max_daily_trades': self.risk_manager.risk_config.get('max_daily_trades', 10),
                'current_drawdown': self.risk_manager.current_drawdown,
                'max_drawdown_limit': self.risk_manager.risk_config.get('max_drawdown_percentage', 0.20),
                'portfolio_metrics': metrics,
                'account_info': account_info
            }
            
        except Exception as e:
            self.logger.error(f"リスク状況取得エラー: {e}")
            return {
                'error': str(e),
                'can_trade': False,
                'risk_reason': 'リスク状況取得エラー'
            }

    def set_emergency_stop(self, enabled: bool = True) -> bool:
        """
        緊急停止フラグの設定
        
        Args:
            enabled: 緊急停止を有効にするか
            
        Returns:
            設定成功か
        """
        try:
            self.emergency_stop = enabled
            status = "有効" if enabled else "無効"
            self.logger.warning(f"緊急停止フラグを{status}にしました")
            
            if enabled:
                # 緊急停止時はすべてのアクティブ注文をキャンセル
                self.cancel_all_orders()
            
            return True
        except Exception as e:
            self.logger.error(f"緊急停止設定エラー: {e}")
            return False

    def get_risk_metrics_for_ui(self) -> Dict[str, Any]:
        """
        UI表示用のリスクメトリクスを取得
        
        Returns:
            UI用リスクメトリクス
        """
        try:
            risk_status = self.get_risk_status()
            account_info = risk_status.get('account_info', {})
            
            # 基本メトリクス
            metrics = {
                'trading_status': {
                    'can_trade': risk_status.get('can_trade', False),
                    'reason': risk_status.get('risk_reason', ''),
                    'emergency_stop': risk_status.get('emergency_stop', False)
                },
                'position_metrics': {
                    'current_positions': risk_status.get('current_positions', 0),
                    'max_positions': risk_status.get('max_positions', 3),
                    'positions_remaining': risk_status.get('max_positions', 3) - risk_status.get('current_positions', 0)
                },
                'trading_limits': {
                    'daily_trades': risk_status.get('daily_trades', 0),
                    'max_daily_trades': risk_status.get('max_daily_trades', 10),
                    'trades_remaining': risk_status.get('max_daily_trades', 10) - risk_status.get('daily_trades', 0)
                },
                'drawdown_metrics': {
                    'current_drawdown': risk_status.get('current_drawdown', 0) * 100,
                    'max_drawdown_limit': risk_status.get('max_drawdown_limit', 0.20) * 100,
                    'drawdown_remaining': (risk_status.get('max_drawdown_limit', 0.20) - risk_status.get('current_drawdown', 0)) * 100
                },
                'margin_metrics': {
                    'margin_level': account_info.get('margin_level', 1.0) * 100,
                    'margin_call_level': self.risk_manager.risk_config.get('margin_call_percentage', 0.05) * 100
                },
                'portfolio_performance': risk_status.get('portfolio_metrics', {}),
                'balance_info': {
                    'total_balance': account_info.get('total_balance', 0),
                    'available_balance': account_info.get('available_balance', 0),
                    'peak_balance': self.risk_manager.peak_balance
                }
            }
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"UI用リスクメトリクス取得エラー: {e}")
            return {
                'error': str(e),
                'trading_status': {'can_trade': False, 'reason': 'メトリクス取得エラー'}
            }
