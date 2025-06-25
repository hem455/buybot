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
from datetime import datetime, timezone, timedelta
from .logger import get_logger
from .utils import AssetHistoryDB
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

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
        
        # 資産履歴データベースを初期化（エラーハンドリング付き）
        try:
            self.asset_history_db = AssetHistoryDB()
            self.logger.info("資産履歴データベースの初期化に成功しました")
        except Exception as e:
            self.logger.error(f"資産履歴データベースの初期化に失敗しました: {e}")
            self.asset_history_db = None
        
        # セッション設定（再試行機能付き）
        self.session = requests.Session()
        try:
            retry_strategy = Retry(
                total=3,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "POST"],  # method_whitelistの新しいパラメータ名
                backoff_factor=1
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
        except Exception as e:
            self.logger.warning(f"HTTP再試行設定に失敗しました（標準設定を使用）: {e}")
        
        # レート制限
        self.last_request_time = 0
        self.min_request_interval = 0.1
        
        # 初期化完了ログ
        self.logger.info(f"GMOクライアント初期化完了 - ベースURL: {self.PRIVATE_BASE_URL}")
    
    def _create_sign(self, text: str) -> str:
        """署名を作成"""
        return hmac.new(
            bytes(self.api_secret, 'utf-8'),
            bytes(text, 'utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _request(self, method: str, base_url: str, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """APIリクエストを送信する内部メソッド"""
        try:
            # レート制限
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.min_request_interval:
                time.sleep(self.min_request_interval - time_since_last)
            
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
            
            if method == 'GET':
                response = self.session.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = self.session.post(url, headers=headers, json=params, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            self.last_request_time = time.time()
            result = response.json()
            self.logger.debug(f"Response: {result}")
            return result

        except requests.exceptions.ConnectionError as e:
            self.logger.warning(f"ネットワーク接続エラー (一時的な可能性): {path} - {str(e)}")
            return None
        except requests.exceptions.Timeout as e:
            self.logger.warning(f"APIタイムアウト: {path} - {str(e)}")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"APIリクエストエラー: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"予期しないエラー: {str(e)}")
            return None
    
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
        try:
            response = self._request('GET', self.PRIVATE_BASE_URL, '/v1/account/assets')
            if response is None:
                self.logger.warning("残高取得: APIレスポンスなし（ネットワーク問題の可能性）")
                return None
            
            if response.get('status') != 0:
                self.logger.error(f"残高取得エラー: {response.get('messages', ['不明なエラー'])}")
                return None
            
            balance_data = {'total_jpy': 0, 'assets': [], 'positions': []}
            for asset in response.get('data', []):
                amount = float(asset.get('amount', 0))
                available = float(asset.get('available', 0))
                symbol = asset.get('symbol')
                jpy_value = amount if symbol == 'JPY' else 0
                balance_data['total_jpy'] += jpy_value
                balance_data['assets'].append({'symbol': symbol, 'amount': amount, 'available': available, 'jpy_value': jpy_value})
            return balance_data
        except Exception as e:
            self.logger.error(f"残高取得エラー: {str(e)}")
            return None
    
    def get_positions(self, symbol: str = 'BTC_JPY') -> List[Dict[str, Any]]:
        """建玉一覧を取得（証拠金取引のポジション）"""
        # レバレッジ銘柄には _JPY が必要
        if not symbol.endswith('_JPY'):
            symbol += '_JPY'
            
        try:
            params = {'symbol': symbol}
            response = self._request('GET', self.PRIVATE_BASE_URL, '/v1/openPositions', params)
            if response is None:
                self.logger.warning(f"ポジション取得: APIレスポンスなし（ネットワーク問題の可能性） - {symbol}")
                return []
            
            if response.get('status') != 0:
                self.logger.warning(f"ポジション取得エラー: {response.get('messages', ['不明なエラー'])} - {symbol}")
                return []
            
            positions = []
            # GMOコインAPIの構造: {"status": 0, "data": [...]} 
            # data は直接リストで、listプロパティではない
            for pos in response.get('data', []):
                position_data = {
                    'symbol': pos.get('symbol'),
                    'side': pos.get('side'),
                    'size': float(pos.get('size', 0)),
                    'price': float(pos.get('price', 0)),
                    'lossGain': float(pos.get('lossGain', 0)),
                    'timestamp': pos.get('timestamp')
                }
                positions.append(position_data)
                self.logger.debug(f"Added position: {position_data}")
            
            self.logger.info(f"取得したポジション数: {len(positions)}")
            return positions
        except Exception as e:
            self.logger.warning(f"ポジション取得エラー: {str(e)}")
            return []
    
    def get_latest_executions(self, symbol: str = 'BTC', count: int = 100) -> List[Dict[str, Any]]:
        """約定履歴を取得"""
        params = {'symbol': symbol, 'count': str(count)}
        result = self._request('GET', self.PRIVATE_BASE_URL, '/v1/latestExecutions', params)
        self.logger.debug(f"Latest executions API response: {result}")
        
        if result.get('status') == 0:
            trades = []
            # GMOコインAPIの構造: {"status": 0, "data": [...]}
            # data は直接リストで、listプロパティではない
            for trade in result.get('data', []):
                trade_data = {
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
                }
                trades.append(trade_data)
                self.logger.debug(f"Added trade: {trade_data}")
            
            self.logger.info(f"取得した取引履歴数: {len(trades)}")
            return trades
        else:
            error_msg = result.get('messages', [{}])[0].get('message_string', 'Unknown error')
            self.logger.warning(f"取引履歴取得エラー: {error_msg}")
            return []
    
    def get_trade_history(self, symbol: str = 'BTC_JPY', count: int = 100) -> List[Dict[str, Any]]:
        """取引履歴を取得（約定履歴のラッパー）"""
        if symbol.endswith('_JPY'):
            symbol = symbol[:-4]
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
        if 'error' in balance_data:
            return []
        
        holdings = []
        for asset in balance_data.get('assets', []):
            if asset['symbol'] != 'JPY' and asset['amount'] > 0:
                # 現在価格を取得
                ticker = self.get_ticker(f"{asset['symbol']}_JPY")
                current_price = ticker.get('last', 0) if ticker else 0
                
                holding = {
                    'symbol': f"{asset['symbol']}_JPY",
                    'side': 'LONG',  # 現物は常にLONG
                    'size': asset['amount'],
                    'price': current_price,  # 現在価格（取得価格不明のため）
                    'lossGain': 0,  # 取得価格不明のため0
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'type': 'SPOT'  # 現物を示すフラグ
                }
                holdings.append(holding)
                self.logger.debug(f"Added spot holding: {holding}")
        
        self.logger.info(f"現物保有数: {len(holdings)}")
        return holdings

    def get_all_positions(self) -> List[Dict[str, Any]]:
        """証拠金取引のポジション + 現物保有を統合取得"""
        try:
            # 証拠金取引のポジション
            margin_positions = self.get_positions()
            
            # 現物保有
            spot_holdings = self.get_spot_holdings()
            
            # 統合
            all_positions = margin_positions + spot_holdings
            self.logger.info(f"全ポジション数: {len(all_positions)} (証拠金: {len(margin_positions)}, 現物: {len(spot_holdings)})")
            
            return all_positions
            
        except Exception as e:
            self.logger.error(f"ポジション統合取得エラー: {e}")
            return []

    def get_today_trade_count(self) -> int:
        """当日の取引回数を取得"""
        try:
            # 今日の日付
            today = datetime.now().strftime('%Y%m%d')
            
            # 当日の約定履歴を取得
            result = self._request('GET', self.PRIVATE_BASE_URL, '/v1/latestExecutions', {
                'count': '100'  # 最大100件取得
            })
            
            if result.get('status') == 0:
                trades = result.get('data', [])
                today_trades = 0
                
                for trade in trades:
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
            if 'error' in current_balance:
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
            result = self._request('GET', self.PRIVATE_BASE_URL, '/v1/activeOrders', {'symbol': symbol})
            
            if result.get('status') == 0:
                orders = []
                for order in result.get('data', []):
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
                
                self.logger.info(f"取得した有効注文数: {len(orders)}")
                return orders
            else:
                error_msg = result.get('messages', [{}])[0].get('message_string', 'Unknown error')
                self.logger.warning(f"有効注文取得エラー: {error_msg}")
                return []
                
        except Exception as e:
            self.logger.error(f"有効注文取得エラー: {e}")
            return []

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """注文をキャンセル"""
        try:
            result = self._request('POST', self.PRIVATE_BASE_URL, '/v1/cancelOrder', {
                'orderId': order_id
            })
            
            if result.get('status') == 0:
                self.logger.info(f"注文キャンセル成功: {order_id}")
                return {'success': True, 'orderId': order_id}
            else:
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
            
            result = self._request('POST', self.PRIVATE_BASE_URL, '/v1/order', order_data)
            
            if result.get('status') == 0:
                order_id = result.get('data')
                self.logger.info(f"注文発注成功: {order_id}")
                return {'success': True, 'orderId': order_id, 'side': side, 'size': size}
            else:
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
                return {}
            
            # 口座情報取得
            balance = self.get_account_balance()
            available_jpy = balance.get('total_jpy', 0)
            
            liquidation_info = {}
            
            for position in positions:
                position_side = position['side']
                entry_price = position['price']
                position_size = position['size']
                
                # 簡易ロスカット計算（証拠金維持率75%として）
                # 実際のGMOコインの計算式とは異なる場合があります
                required_margin = entry_price * position_size * 0.04  # レバレッジ25倍の場合
                liquidation_margin_rate = 0.75  # 75%
                
                if position_side == 'BUY':
                    # ロング：価格下落でロスカット
                    liquidation_price = entry_price * (1 - (available_jpy * liquidation_margin_rate) / (entry_price * position_size))
                else:
                    # ショート：価格上昇でロスカット
                    liquidation_price = entry_price * (1 + (available_jpy * liquidation_margin_rate) / (entry_price * position_size))
                
                liquidation_info[position.get('symbol', symbol)] = {
                    'liquidation_price': max(liquidation_price, 0),
                    'position_side': position_side,
                    'entry_price': entry_price,
                    'current_margin_rate': (available_jpy / required_margin) * 100 if required_margin > 0 else 0
                }
            
            self.logger.info(f"ロスカット価格計算完了: {len(liquidation_info)}ポジション")
            return liquidation_info
            
        except Exception as e:
            self.logger.error(f"ロスカット価格計算エラー: {e}")
            return {}
    
    # --- 資産履歴管理機能 ---
    def calculate_total_assets(self) -> Dict[str, Any]:
        """
        総資産を計算（現在の実装ロジックと同じ）
        
        Returns:
            総資産情報
        """
        try:
            # 残高情報を取得
            balance = self.get_account_balance()
            if 'error' in balance:
                return {'error': balance['error']}
            
            jpy_balance = balance.get('total_jpy', 0)
            
            # 現物保有の評価額を計算
            spot_value = 0
            assets = balance.get('assets', [])
            asset_breakdown = {}
            
            for asset in assets:
                if asset['symbol'] != 'JPY' and asset['amount'] > 0:
                    # 現在価格を取得
                    ticker = self.get_ticker(f"{asset['symbol']}_JPY")
                    if ticker:
                        current_price = ticker.get('last', 0)
                        value = current_price * asset['amount']
                        spot_value += value
                        asset_breakdown[asset['symbol']] = {
                            'amount': asset['amount'],
                            'price': current_price,
                            'value': value
                        }
            
            # 証拠金取引の評価損益を計算
            margin_pnl = 0
            positions = self.get_all_positions()
            margin_positions = [p for p in positions if p.get('type') != 'SPOT']
            for pos in margin_positions:
                margin_pnl += pos.get('lossGain', 0)
            
            # 総資産 = JPY残高 + 現物評価額 + 証拠金損益
            total_assets = jpy_balance + spot_value + margin_pnl
            
            return {
                'total_assets': total_assets,
                'jpy_balance': jpy_balance,
                'spot_value': spot_value,
                'margin_pnl': margin_pnl,
                'asset_breakdown': asset_breakdown
            }
            
        except Exception as e:
            self.logger.error(f"総資産計算エラー: {e}")
            return {'error': str(e)}
    
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
            
            if 'error' in asset_data:
                self.logger.error(f"総資産保存失敗: {asset_data['error']}")
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
