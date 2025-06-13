"""
グリッドトレーディング戦略

価格の一定範囲内で複数の買い注文と売り注文をグリッド状に配置し、
価格の上下動から利益を得る戦略。
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple, Optional, List
from dataclasses import dataclass
from datetime import datetime

from .base_strategy import BaseStrategy, Signal
from ..logger import get_logger


@dataclass
class GridLevel:
    """グリッドレベルを表すデータクラス"""
    price: float
    side: str  # 'BUY' or 'SELL'
    filled: bool = False
    order_id: Optional[str] = None
    timestamp: Optional[datetime] = None


class GridTradingStrategy(BaseStrategy):
    """
    グリッドトレーディング戦略
    
    一定の価格間隔でグリッドを作成し、
    価格が下がったら買い、上がったら売りを繰り返す。
    """
    
    def __init__(self, strategy_id: str = 'grid_trading', params: Optional[Dict[str, Any]] = None):
        """
        初期化
        
        Args:
            strategy_id: 戦略ID
            params: 戦略パラメータ
        """
        # デフォルトパラメータ
        default_params = {
            'grid_count': 10,           # グリッドの数
            'grid_spacing_pct': 1.0,    # グリッド間隔（%）
            'position_size_per_grid': 0.001,  # 各グリッドのポジションサイズ（BTC）
            'price_range_pct': 10.0,    # 中心価格からの範囲（±%）
            'rebalance_threshold': 5.0, # リバランス閾値（%）
            'use_dynamic_grid': True,   # 動的グリッド調整を使用
            'volatility_adjustment': True,  # ボラティリティに応じて間隔を調整
        }
        
        super().__init__(strategy_id, {**default_params, **(params or {})})
        
        # グリッドの状態管理
        self.grid_levels: List[GridLevel] = []
        self.center_price: Optional[float] = None
        self.last_rebalance_price: Optional[float] = None
        self.grid_profits: float = 0.0
        self.active_orders: Dict[str, GridLevel] = {}
        
        self.logger.info(f"グリッドトレーディング戦略を初期化: {self.params}")
    
    def _initialize_grid(self, current_price: float, volatility: Optional[float] = None) -> None:
        """
        グリッドを初期化する
        
        Args:
            current_price: 現在価格
            volatility: ボラティリティ（ATRなど）
        """
        self.center_price = current_price
        self.last_rebalance_price = current_price
        self.grid_levels = []
        
        # グリッド間隔を計算
        spacing_pct = self.params['grid_spacing_pct']
        
        # ボラティリティ調整
        if self.params['volatility_adjustment'] and volatility:
            # ボラティリティが高い時は間隔を広げる
            volatility_factor = volatility / current_price * 100  # %換算
            spacing_pct = spacing_pct * (1 + volatility_factor * 0.5)
        
        # グリッドレベルを生成
        grid_count = self.params['grid_count']
        
        # 上側のグリッド（売り注文）
        for i in range(1, grid_count // 2 + 1):
            price = current_price * (1 + spacing_pct * i / 100)
            self.grid_levels.append(GridLevel(price=price, side='SELL'))
        
        # 下側のグリッド（買い注文）
        for i in range(1, grid_count // 2 + 1):
            price = current_price * (1 - spacing_pct * i / 100)
            self.grid_levels.append(GridLevel(price=price, side='BUY'))
        
        # 価格でソート
        self.grid_levels.sort(key=lambda x: x.price)
        
        self.logger.info(f"グリッドを初期化: 中心価格={current_price:.0f}, レベル数={len(self.grid_levels)}")
    
    def _should_rebalance_grid(self, current_price: float) -> bool:
        """
        グリッドのリバランスが必要かチェック
        
        Args:
            current_price: 現在価格
        
        Returns:
            リバランスが必要か
        """
        if not self.center_price:
            return True
        
        # 中心価格からの乖離率
        deviation_pct = abs((current_price - self.center_price) / self.center_price) * 100
        
        return deviation_pct > self.params['rebalance_threshold']
    
    def _find_triggered_levels(self, current_price: float, prev_price: float) -> List[GridLevel]:
        """
        トリガーされたグリッドレベルを検出
        
        Args:
            current_price: 現在価格
            prev_price: 前回価格
        
        Returns:
            トリガーされたレベルのリスト
        """
        triggered = []
        
        for level in self.grid_levels:
            if level.filled:
                continue
            
            # 買いレベル: 価格が下から上にクロス
            if level.side == 'BUY':
                if prev_price > level.price >= current_price:
                    triggered.append(level)
            
            # 売りレベル: 価格が上から下にクロス
            elif level.side == 'SELL':
                if prev_price < level.price <= current_price:
                    triggered.append(level)
        
        return triggered
    
    def generate_signal(self, df: pd.DataFrame, current_position: Dict[str, Any], 
                       account_info: Dict[str, Any]) -> Tuple[Signal, Dict[str, Any]]:
        """
        シグナルを生成する
        
        Args:
            df: OHLCVデータフレーム
            current_position: 現在のポジション情報
            account_info: 口座情報
        
        Returns:
            (シグナル, 詳細情報)のタプル
        """
        # データチェック
        if len(df) < 2:
            return Signal.HOLD, {'reason': 'データ不足'}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        current_price = latest['close']
        prev_price = prev['close']
        
        # ボラティリティ指標（ATR）
        volatility = latest.get('atr', None)
        
        # グリッドの初期化またはリバランス
        if not self.grid_levels or self._should_rebalance_grid(current_price):
            self._initialize_grid(current_price, volatility)
            return Signal.HOLD, {
                'action': 'grid_initialized',
                'center_price': self.center_price,
                'grid_count': len(self.grid_levels)
            }
        
        # トリガーされたレベルをチェック
        triggered_levels = self._find_triggered_levels(current_price, prev_price)
        
        if not triggered_levels:
            return Signal.HOLD, {
                'reason': 'グリッドレベルに到達していない',
                'current_price': current_price,
                'nearest_buy': min([l.price for l in self.grid_levels if l.side == 'BUY' and not l.filled], default=0),
                'nearest_sell': min([l.price for l in self.grid_levels if l.side == 'SELL' and not l.filled], default=0)
            }
        
        # 最も近いトリガーレベルを選択
        triggered_level = min(triggered_levels, key=lambda l: abs(l.price - current_price))
        
        # シグナルを生成
        if triggered_level.side == 'BUY':
            signal = Signal.BUY
            action = 'グリッド買い'
        else:
            signal = Signal.SELL
            action = 'グリッド売り'
        
        # レベルを使用済みにマーク
        triggered_level.filled = True
        triggered_level.timestamp = datetime.now()
        
        details = {
            'action': action,
            'grid_price': triggered_level.price,
            'current_price': current_price,
            'grid_spacing': self.params['grid_spacing_pct'],
            'position_size': self.params['position_size_per_grid'],
            'active_grids': sum(1 for l in self.grid_levels if l.filled),
            'total_grids': len(self.grid_levels)
        }
        
        self.log_signal(signal, details)
        return signal, details
    
    def calculate_confidence(self, df: pd.DataFrame, signal: Signal) -> float:
        """
        シグナルの確信度を計算する
        
        Args:
            df: データフレーム
            signal: シグナル
        
        Returns:
            確信度（0.0〜1.0）
        """
        # グリッドトレーディングは機械的な戦略なので高い確信度
        base_confidence = 0.8
        
        # ボラティリティが高い場合は確信度を下げる
        if 'atr' in df.columns:
            latest = df.iloc[-1]
            atr_pct = (latest['atr'] / latest['close']) * 100
            
            if atr_pct > 5:  # 高ボラティリティ
                base_confidence *= 0.8
            elif atr_pct < 1:  # 低ボラティリティ
                base_confidence *= 0.9
        
        return base_confidence
    
    def get_recommended_stop_loss(self, df: pd.DataFrame, signal: Signal) -> Optional[float]:
        """
        推奨ストップロス価格を取得する
        
        Args:
            df: データフレーム
            signal: シグナル
        
        Returns:
            ストップロス価格
        """
        # グリッドトレーディングでは個別のストップロスは使用しない
        # 代わりに全体のリスク管理で対応
        return None
    
    def get_grid_statistics(self) -> Dict[str, Any]:
        """
        グリッドの統計情報を取得
        
        Returns:
            統計情報
        """
        filled_grids = [l for l in self.grid_levels if l.filled]
        buy_grids = [l for l in filled_grids if l.side == 'BUY']
        sell_grids = [l for l in filled_grids if l.side == 'SELL']
        
        return {
            'total_grids': len(self.grid_levels),
            'filled_grids': len(filled_grids),
            'buy_grids_filled': len(buy_grids),
            'sell_grids_filled': len(sell_grids),
            'center_price': self.center_price,
            'grid_profits': self.grid_profits,
            'utilization_rate': len(filled_grids) / len(self.grid_levels) * 100 if self.grid_levels else 0
        }
