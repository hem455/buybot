"""
GMOコイン WebSocket API データ取得モジュール

GMOコインのWebSocket APIを使用してリアルタイムデータを取得するモジュール。
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, Callable, Optional, List
import websockets
from websockets.exceptions import ConnectionClosed

from .base import BaseDataFetcher
from ..logger import get_logger, log_error


class GMOCoinWebSocketFetcher:
    """GMOコイン WebSocket API データ取得クラス"""
    
    def __init__(self, config):
        """初期化"""
        self.config = config
        self.logger = get_logger()
        self.exchange_config = config.get_exchange_config()
        self.trading_config = config.get_trading_config()
        
        # WebSocket設定
        self.ws_url = self.exchange_config.get('websocket_endpoint', 'wss://api.coin.z.com/ws/public/v1')
        self.private_ws_url = self.exchange_config.get('private_ws_endpoint', 'wss://api.coin.z.com/ws/private/v1')
        
        # 接続管理
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.private_ws: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.is_private_connected = False
        
        # 設定
        ws_config = config.get('data_fetcher.websocket', {})
        self.channels = ws_config.get('channels', ['ticker', 'trades', 'orderbooks'])
        self.reconnect_interval = ws_config.get('reconnect_interval', 5)
        self.max_reconnect_attempts = ws_config.get('max_reconnect_attempts', 10)
        self.heartbeat_interval = ws_config.get('heartbeat_interval', 30)
        
        # コールバック
        self.callbacks: Dict[str, List[Callable]] = {
            'ticker': [],
            'trades': [],
            'orderbooks': [],
            'executions': [],
            'orders': [],
            'positions': []
        }
        
        # データバッファ
        self.latest_ticker: Dict[str, Dict[str, Any]] = {}
        self.latest_orderbook: Dict[str, Dict[str, Any]] = {}
        self.latest_trades: Dict[str, List[Dict[str, Any]]] = {}
    
    def register_callback(self, channel: str, callback: Callable) -> None:
        """
        コールバック関数を登録する
        
        Args:
            channel: チャンネル名
            callback: コールバック関数
        """
        if channel in self.callbacks:
            self.callbacks[channel].append(callback)
        else:
            self.logger.warning(f"不明なチャンネル: {channel}")
    
    async def connect(self) -> None:
        """WebSocket接続を開始する"""
        # パブリックWebSocket接続
        asyncio.create_task(self._connect_public())
        
        # プライベートWebSocket接続（APIキーが設定されている場合）
        credentials = self.config.get_api_credentials()
        if credentials['api_key'] and credentials['api_secret']:
            asyncio.create_task(self._connect_private())
    
    async def _connect_public(self) -> None:
        """パブリックWebSocket接続"""
        reconnect_count = 0
        
        while reconnect_count < self.max_reconnect_attempts:
            try:
                self.logger.info("パブリックWebSocketに接続中...")
                self.ws = await websockets.connect(self.ws_url)
                self.is_connected = True
                reconnect_count = 0
                self.logger.info("パブリックWebSocket接続成功")
                
                # チャンネル購読
                await self._subscribe_channels()
                
                # ハートビートタスクを開始
                heartbeat_task = asyncio.create_task(self._heartbeat())
                
                # メッセージ受信ループ
                await self._receive_messages()
                
            except ConnectionClosed:
                self.logger.warning("パブリックWebSocket接続が切断されました")
                self.is_connected = False
                
            except Exception as e:
                self.logger.error(f"パブリックWebSocket接続エラー: {e}")
                self.is_connected = False
            
            # 再接続待機
            reconnect_count += 1
            if reconnect_count < self.max_reconnect_attempts:
                wait_time = self.reconnect_interval * reconnect_count
                self.logger.info(f"{wait_time}秒後に再接続を試みます... ({reconnect_count}/{self.max_reconnect_attempts})")
                await asyncio.sleep(wait_time)
        
        self.logger.error("パブリックWebSocket接続の最大再試行回数に達しました")
    
    async def _connect_private(self) -> None:
        """プライベートWebSocket接続"""
        # プライベートWebSocketの実装は後で追加
        pass
    
    async def _subscribe_channels(self) -> None:
        """チャンネルを購読する"""
        symbol = self.trading_config.get('symbol', 'BTC_JPY')
        
        for channel in self.channels:
            if channel == 'ticker':
                await self._send_message({
                    "command": "subscribe",
                    "channel": "ticker",
                    "symbol": symbol
                })
            elif channel == 'trades':
                await self._send_message({
                    "command": "subscribe",
                    "channel": "trades",
                    "symbol": symbol
                })
            elif channel == 'orderbooks':
                await self._send_message({
                    "command": "subscribe",
                    "channel": "orderbooks",
                    "symbol": symbol
                })
    
    async def _send_message(self, message: Dict[str, Any]) -> None:
        """メッセージを送信する"""
        if self.ws and self.is_connected:
            await self.ws.send(json.dumps(message))
            self.logger.debug(f"メッセージ送信: {message}")
    
    async def _heartbeat(self) -> None:
        """ハートビートを送信する"""
        while self.is_connected:
            try:
                await self.ws.pong()
                await asyncio.sleep(self.heartbeat_interval)
            except Exception as e:
                self.logger.error(f"ハートビートエラー: {e}")
                break
    
    async def _receive_messages(self) -> None:
        """メッセージを受信する"""
        async for message in self.ws:
            try:
                data = json.loads(message)
                await self._handle_message(data)
            except json.JSONDecodeError as e:
                self.logger.error(f"JSONデコードエラー: {e}")
            except Exception as e:
                self.logger.error(f"メッセージ処理エラー: {e}")
    
    async def _handle_message(self, data: Dict[str, Any]) -> None:
        """メッセージを処理する"""
        channel = data.get('channel')
        
        if channel == 'ticker':
            await self._handle_ticker(data)
        elif channel == 'trades':
            await self._handle_trades(data)
        elif channel == 'orderbooks':
            await self._handle_orderbook(data)
        elif channel == 'execution':
            await self._handle_execution(data)
        elif channel == 'order':
            await self._handle_order(data)
        elif channel == 'position':
            await self._handle_position(data)
        else:
            self.logger.debug(f"未処理のチャンネル: {channel}")
    
    async def _handle_ticker(self, data: Dict[str, Any]) -> None:
        """ティッカーデータを処理する"""
        symbol = data.get('symbol')
        if not symbol:
            return
        
        ticker = {
            'symbol': symbol,
            'ask': float(data['ask']),
            'bid': float(data['bid']),
            'last': float(data['last']),
            'high': float(data['high']),
            'low': float(data['low']),
            'volume': float(data['volume']),
            'timestamp': pd.to_datetime(data['timestamp'])
        }
        
        # 最新データを保存
        self.latest_ticker[symbol] = ticker
        
        # コールバックを実行
        for callback in self.callbacks['ticker']:
            try:
                await callback(ticker)
            except Exception as e:
                self.logger.error(f"ティッカーコールバックエラー: {e}")
    
    async def _handle_trades(self, data: Dict[str, Any]) -> None:
        """取引データを処理する"""
        symbol = data.get('symbol')
        if not symbol:
            return
        
        trades = []
        for trade_data in data.get('trades', []):
            trade = {
                'symbol': symbol,
                'price': float(trade_data['price']),
                'size': float(trade_data['size']),
                'side': trade_data['side'],
                'timestamp': pd.to_datetime(trade_data['timestamp'])
            }
            trades.append(trade)
        
        # 最新データを保存（最新100件のみ保持）
        if symbol not in self.latest_trades:
            self.latest_trades[symbol] = []
        self.latest_trades[symbol].extend(trades)
        self.latest_trades[symbol] = self.latest_trades[symbol][-100:]
        
        # コールバックを実行
        for callback in self.callbacks['trades']:
            try:
                await callback(trades)
            except Exception as e:
                self.logger.error(f"取引コールバックエラー: {e}")
    
    async def _handle_orderbook(self, data: Dict[str, Any]) -> None:
        """オーダーブックデータを処理する"""
        symbol = data.get('symbol')
        if not symbol:
            return
        
        orderbook = {
            'symbol': symbol,
            'asks': [[float(ask['price']), float(ask['size'])] for ask in data.get('asks', [])],
            'bids': [[float(bid['price']), float(bid['size'])] for bid in data.get('bids', [])],
            'timestamp': datetime.now(timezone.utc)
        }
        
        # 最新データを保存
        self.latest_orderbook[symbol] = orderbook
        
        # コールバックを実行
        for callback in self.callbacks['orderbooks']:
            try:
                await callback(orderbook)
            except Exception as e:
                self.logger.error(f"オーダーブックコールバックエラー: {e}")
    
    async def _handle_execution(self, data: Dict[str, Any]) -> None:
        """約定データを処理する"""
        # コールバックを実行
        for callback in self.callbacks['executions']:
            try:
                await callback(data)
            except Exception as e:
                self.logger.error(f"約定コールバックエラー: {e}")
    
    async def _handle_order(self, data: Dict[str, Any]) -> None:
        """注文データを処理する"""
        # コールバックを実行
        for callback in self.callbacks['orders']:
            try:
                await callback(data)
            except Exception as e:
                self.logger.error(f"注文コールバックエラー: {e}")
    
    async def _handle_position(self, data: Dict[str, Any]) -> None:
        """ポジションデータを処理する"""
        # コールバックを実行
        for callback in self.callbacks['positions']:
            try:
                await callback(data)
            except Exception as e:
                self.logger.error(f"ポジションコールバックエラー: {e}")
    
    async def disconnect(self) -> None:
        """WebSocket接続を切断する"""
        self.is_connected = False
        self.is_private_connected = False
        
        if self.ws:
            await self.ws.close()
            self.ws = None
        
        if self.private_ws:
            await self.private_ws.close()
            self.private_ws = None
        
        self.logger.info("WebSocket接続を切断しました")
    
    def get_latest_ticker(self, symbol: str) -> Optional[Dict[str, Any]]:
        """最新のティッカーデータを取得する"""
        return self.latest_ticker.get(symbol)
    
    def get_latest_orderbook(self, symbol: str) -> Optional[Dict[str, Any]]:
        """最新のオーダーブックデータを取得する"""
        return self.latest_orderbook.get(symbol)
    
    def get_latest_trades(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """最新の取引データを取得する"""
        trades = self.latest_trades.get(symbol, [])
        return trades[-limit:] if trades else []
