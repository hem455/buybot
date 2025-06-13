"""
注文実行モジュール

GMOコインAPIを使用して注文の発注、管理、約定確認を行うモジュール。
"""

import asyncio
import time
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from enum import Enum
import uuid

from ..config_manager import get_config_manager
from ..logger import get_logger, log_order, log_trade, log_error
from ..data_fetcher import GMOCoinRESTFetcher
from ..strategy import Signal


class OrderType(Enum):
    """注文タイプ"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


class OrderSide(Enum):
    """注文サイド"""
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    """注文ステータス"""
    PENDING = "PENDING"
    ORDERED = "ORDERED"
    EXECUTED = "EXECUTED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class OrderExecutor:
    """注文実行クラス"""
    
    def __init__(self):
        """初期化"""
        self.config = get_config_manager()
        self.logger = get_logger()
        self.trading_config = self.config.get_trading_config()
        
        # 注文管理
        self.active_orders: Dict[str, Dict[str, Any]] = {}
        self.order_history: List[Dict[str, Any]] = []
        
        # API接続
        self.rest_api = GMOCoinRESTFetcher()
    
    async def execute_signal(self, signal: Signal, position_size: float, 
                           stop_loss: Optional[float] = None,
                           take_profit: Optional[float] = None) -> Dict[str, Any]:
        """
        シグナルに基づいて注文を実行する
        
        Args:
            signal: シグナル
            position_size: ポジションサイズ
            stop_loss: ストップロス価格
            take_profit: テイクプロフィット価格
        
        Returns:
            実行結果
        """
        result = {
            'success': False,
            'signal': signal.value,
            'orders': [],
            'error': None
        }
        
        try:
            # ティッカー情報を取得
            ticker = await self.rest_api.fetch_ticker()
            if not ticker:
                raise Exception("ティッカー情報の取得に失敗しました")
            
            current_price = ticker['last']
            
            # シグナルに応じて注文を作成
            if signal == Signal.BUY:
                # 買い注文
                order = await self._create_order(
                    OrderSide.BUY, 
                    OrderType.MARKET, 
                    position_size,
                    price=None
                )
                result['orders'].append(order)
                
                # ストップロス注文
                if stop_loss:
                    sl_order = await self._create_stop_order(
                        OrderSide.SELL,
                        position_size,
                        stop_loss,
                        parent_order_id=order['order_id']
                    )
                    result['orders'].append(sl_order)
                
                # テイクプロフィット注文
                if take_profit:
                    tp_order = await self._create_limit_order(
                        OrderSide.SELL,
                        position_size,
                        take_profit,
                        parent_order_id=order['order_id']
                    )
                    result['orders'].append(tp_order)
            
            elif signal == Signal.SELL:
                # 売り注文
                order = await self._create_order(
                    OrderSide.SELL,
                    OrderType.MARKET,
                    position_size,
                    price=None
                )
                result['orders'].append(order)
                
                # ストップロス注文
                if stop_loss:
                    sl_order = await self._create_stop_order(
                        OrderSide.BUY,
                        position_size,
                        stop_loss,
                        parent_order_id=order['order_id']
                    )
                    result['orders'].append(sl_order)
                
                # テイクプロフィット注文
                if take_profit:
                    tp_order = await self._create_limit_order(
                        OrderSide.BUY,
                        position_size,
                        take_profit,
                        parent_order_id=order['order_id']
                    )
                    result['orders'].append(tp_order)
            
            elif signal in [Signal.CLOSE_LONG, Signal.CLOSE_SHORT, Signal.CLOSE_ALL]:
                # ポジションクローズ
                positions = await self.rest_api.fetch_positions()
                
                for position in positions:
                    if signal == Signal.CLOSE_ALL or \
                       (signal == Signal.CLOSE_LONG and position['side'] == 'BUY') or \
                       (signal == Signal.CLOSE_SHORT and position['side'] == 'SELL'):
                        
                        close_side = OrderSide.SELL if position['side'] == 'BUY' else OrderSide.BUY
                        close_order = await self._create_order(
                            close_side,
                            OrderType.MARKET,
                            position['size'],
                            price=None
                        )
                        result['orders'].append(close_order)
            
            result['success'] = True
            
        except Exception as e:
            result['error'] = str(e)
            log_error('ORDER_EXECUTION_ERROR', str(e), {
                'signal': signal.value,
                'position_size': position_size
            })
        
        return result
    
    async def _create_order(self, side: OrderSide, order_type: OrderType,
                          size: float, price: Optional[float] = None) -> Dict[str, Any]:
        """
        注文を作成する
        
        Args:
            side: 注文サイド
            order_type: 注文タイプ
            size: 注文サイズ
            price: 指値価格（成行注文の場合はNone）
        
        Returns:
            注文情報
        """
        # 注文IDを生成
        order_id = str(uuid.uuid4())
        
        # 注文情報を作成
        order_info = {
            'order_id': order_id,
            'symbol': self.trading_config.get('symbol', 'BTC_JPY'),
            'side': side.value,
            'order_type': order_type.value,
            'size': size,
            'price': price,
            'status': OrderStatus.PENDING.value,
            'created_at': datetime.now(),
            'executed_size': 0,
            'executed_price': 0,
            'fee': 0
        }
        
        # 注文を送信
        try:
            # GMOコインAPIのパラメータを構築
            params = {
                'symbol': order_info['symbol'],
                'side': side.value,
                'executionType': order_type.value,
                'size': str(size)
            }
            
            if order_type == OrderType.LIMIT and price:
                params['price'] = str(int(price))
            
            # APIを呼び出し
            response = await self.rest_api._request(
                'POST', 
                '/v1/order',
                params,
                is_private=True
            )
            
            # レスポンスから注文IDを取得
            if response and 'data' in response:
                order_info['exchange_order_id'] = response['data']
                order_info['status'] = OrderStatus.ORDERED.value
                
                # アクティブ注文に追加
                self.active_orders[order_id] = order_info
                
                # ログに記録
                log_order('PLACED', order_info)
            else:
                order_info['status'] = OrderStatus.FAILED.value
                order_info['error'] = 'APIレスポンスが不正です'
                
        except Exception as e:
            order_info['status'] = OrderStatus.FAILED.value
            order_info['error'] = str(e)
            log_error('ORDER_CREATION_ERROR', str(e), order_info)
        
        # 履歴に追加
        self.order_history.append(order_info)
        
        return order_info
    
    async def _create_stop_order(self, side: OrderSide, size: float, 
                               stop_price: float, parent_order_id: str) -> Dict[str, Any]:
        """
        ストップ注文を作成する
        
        Args:
            side: 注文サイド
            size: 注文サイズ
            stop_price: ストップ価格
            parent_order_id: 親注文ID
        
        Returns:
            注文情報
        """
        # GMOコインではストップ注文は逆指値として実装
        order_info = await self._create_order(
            side,
            OrderType.STOP,
            size,
            price=stop_price
        )
        
        order_info['parent_order_id'] = parent_order_id
        order_info['order_purpose'] = 'STOP_LOSS'
        
        return order_info
    
    async def _create_limit_order(self, side: OrderSide, size: float,
                                limit_price: float, parent_order_id: str) -> Dict[str, Any]:
        """
        指値注文を作成する（テイクプロフィット用）
        
        Args:
            side: 注文サイド
            size: 注文サイズ
            limit_price: 指値価格
            parent_order_id: 親注文ID
        
        Returns:
            注文情報
        """
        order_info = await self._create_order(
            side,
            OrderType.LIMIT,
            size,
            price=limit_price
        )
        
        order_info['parent_order_id'] = parent_order_id
        order_info['order_purpose'] = 'TAKE_PROFIT'
        
        return order_info
    
    async def check_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        注文ステータスを確認する
        
        Args:
            order_id: 注文ID
        
        Returns:
            注文ステータス情報
        """
        if order_id not in self.active_orders:
            return {'status': 'NOT_FOUND', 'error': '注文が見つかりません'}
        
        order_info = self.active_orders[order_id]
        
        try:
            # GMOコインAPIで注文状態を確認
            params = {'orderId': order_info.get('exchange_order_id')}
            response = await self.rest_api._request(
                'GET',
                '/v1/activeOrders',
                params,
                is_private=True
            )
            
            if response and 'data' in response and 'list' in response['data']:
                orders = response['data']['list']
                
                if not orders:
                    # アクティブ注文にない場合は約定済みの可能性
                    order_info['status'] = OrderStatus.EXECUTED.value
                    await self._check_execution_details(order_info)
                else:
                    # 注文状態を更新
                    for api_order in orders:
                        if api_order['orderId'] == order_info['exchange_order_id']:
                            order_info['status'] = self._map_order_status(api_order['status'])
                            order_info['executed_size'] = float(api_order.get('executedSize', 0))
                            break
            
            # 約定済みの場合は履歴に移動
            if order_info['status'] == OrderStatus.EXECUTED.value:
                del self.active_orders[order_id]
                log_order('FILLED', order_info)
            
            return order_info
            
        except Exception as e:
            log_error('ORDER_STATUS_CHECK_ERROR', str(e), {'order_id': order_id})
            return {'status': 'ERROR', 'error': str(e)}
    
    async def _check_execution_details(self, order_info: Dict[str, Any]) -> None:
        """
        約定詳細を確認する
        
        Args:
            order_info: 注文情報
        """
        try:
            # 約定履歴を取得
            params = {'orderId': order_info.get('exchange_order_id')}
            response = await self.rest_api._request(
                'GET',
                '/v1/executions',
                params,
                is_private=True
            )
            
            if response and 'data' in response and 'list' in response['data']:
                executions = response['data']['list']
                
                # 約定情報を集計
                total_size = 0
                total_value = 0
                total_fee = 0
                
                for execution in executions:
                    exec_size = float(execution['size'])
                    exec_price = float(execution['price'])
                    exec_fee = float(execution.get('fee', 0))
                    
                    total_size += exec_size
                    total_value += exec_size * exec_price
                    total_fee += exec_fee
                
                if total_size > 0:
                    order_info['executed_size'] = total_size
                    order_info['executed_price'] = total_value / total_size
                    order_info['fee'] = total_fee
                    
                    # 取引ログを記録
                    log_trade({
                        'timestamp': datetime.now().isoformat(),
                        'pair': order_info['symbol'],
                        'side': order_info['side'],
                        'quantity': total_size,
                        'price': order_info['executed_price'],
                        'fee': total_fee,
                        'order_id': order_info['order_id'],
                        'execution_id': order_info['exchange_order_id']
                    })
                    
        except Exception as e:
            log_error('EXECUTION_DETAILS_CHECK_ERROR', str(e), {'order_info': order_info})
    
    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        注文をキャンセルする
        
        Args:
            order_id: 注文ID
        
        Returns:
            キャンセル結果
        """
        if order_id not in self.active_orders:
            return {'success': False, 'error': '注文が見つかりません'}
        
        order_info = self.active_orders[order_id]
        
        try:
            # GMOコインAPIでキャンセル
            params = {'orderId': order_info.get('exchange_order_id')}
            response = await self.rest_api._request(
                'POST',
                '/v1/cancelOrder',
                params,
                is_private=True
            )
            
            if response:
                order_info['status'] = OrderStatus.CANCELED.value
                del self.active_orders[order_id]
                
                log_order('CANCELED', order_info)
                
                return {'success': True, 'order_info': order_info}
            else:
                return {'success': False, 'error': 'キャンセルに失敗しました'}
                
        except Exception as e:
            log_error('ORDER_CANCEL_ERROR', str(e), {'order_id': order_id})
            return {'success': False, 'error': str(e)}
    
    async def cancel_all_orders(self) -> Dict[str, Any]:
        """
        すべての注文をキャンセルする
        
        Returns:
            キャンセル結果
        """
        results = {
            'success': True,
            'canceled': [],
            'failed': []
        }
        
        for order_id in list(self.active_orders.keys()):
            result = await self.cancel_order(order_id)
            if result['success']:
                results['canceled'].append(order_id)
            else:
                results['failed'].append({
                    'order_id': order_id,
                    'error': result.get('error')
                })
                results['success'] = False
        
        return results
    
    def _map_order_status(self, api_status: str) -> str:
        """
        APIステータスを内部ステータスにマッピング
        
        Args:
            api_status: APIステータス
        
        Returns:
            内部ステータス
        """
        status_map = {
            'WAITING': OrderStatus.ORDERED.value,
            'ORDERED': OrderStatus.ORDERED.value,
            'EXECUTED': OrderStatus.EXECUTED.value,
            'CANCELED': OrderStatus.CANCELED.value,
            'EXPIRED': OrderStatus.EXPIRED.value
        }
        
        return status_map.get(api_status, OrderStatus.PENDING.value)
    
    def get_active_orders(self) -> List[Dict[str, Any]]:
        """アクティブな注文を取得する"""
        return list(self.active_orders.values())
    
    def get_order_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """注文履歴を取得する"""
        return self.order_history[-limit:]
