"""
戦略基底クラス

売買戦略の基底クラスを定義する。
すべての戦略はこのクラスを継承して実装する。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import pandas as pd
from enum import Enum

from ..config_manager import get_config_manager
from ..logger import get_logger, log_signal


class Signal(Enum):
    """シグナルタイプ"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CLOSE_LONG = "CLOSE_LONG"
    CLOSE_SHORT = "CLOSE_SHORT"
    CLOSE_ALL = "CLOSE_ALL"


class BaseStrategy(ABC):
    """戦略基底クラス"""
    
    def __init__(self, strategy_id: str, params: Optional[Dict[str, Any]] = None):
        """
        初期化
        
        Args:
            strategy_id: 戦略ID
            params: 戦略パラメータ（省略時は設定から取得）
        """
        self.config = get_config_manager()
        self.logger = get_logger()
        self.strategy_id = strategy_id
        
        # 戦略設定を取得
        strategy_config = self.config.get_strategy_config(strategy_id)
        self.name = strategy_config.get('name', strategy_id)
        self.description = strategy_config.get('description', '')
        
        # パラメータを設定
        default_params = strategy_config.get('parameters', {})
        self.params = {**default_params, **(params or {})}
        
        # 状態管理
        self.position_info = {
            'side': None,  # 'LONG', 'SHORT', None
            'size': 0,
            'entry_price': 0,
            'entry_time': None
        }
        
        self.logger.info(f"戦略を初期化しました: {self.name} (ID: {self.strategy_id})")
    
    @abstractmethod
    def generate_signal(self, df: pd.DataFrame, current_position: Dict[str, Any], 
                       account_info: Dict[str, Any]) -> Tuple[Signal, Dict[str, Any]]:
        """
        シグナルを生成する
        
        Args:
            df: 指標が計算されたOHLCVデータフレーム
            current_position: 現在のポジション情報
            account_info: 口座情報
        
        Returns:
            (シグナル, 詳細情報)のタプル
        """
        pass
    
    def update_position(self, position_info: Dict[str, Any]) -> None:
        """
        ポジション情報を更新する
        
        Args:
            position_info: ポジション情報
        """
        self.position_info = position_info.copy()
    
    def log_signal(self, signal: Signal, details: Dict[str, Any]) -> None:
        """
        シグナルをログに記録する
        
        Args:
            signal: シグナル
            details: 詳細情報
        """
        log_signal(signal.value, self.name, details)
    
    def validate_signal(self, signal: Signal, current_position: Dict[str, Any]) -> bool:
        """
        シグナルが有効かどうかを検証する
        
        Args:
            signal: シグナル
            current_position: 現在のポジション情報
        
        Returns:
            有効かどうか
        """
        # ポジションがない場合
        if not current_position or current_position.get('side') is None:
            # CLOSEシグナルは無効
            if signal in [Signal.CLOSE_LONG, Signal.CLOSE_SHORT, Signal.CLOSE_ALL]:
                return False
            # BUY/SELLシグナルは有効
            return signal in [Signal.BUY, Signal.SELL]
        
        # ロングポジションがある場合
        if current_position.get('side') == 'LONG':
            # 追加のBUYシグナルは無効（ドテンなし）
            if signal == Signal.BUY:
                return False
            # SELL, CLOSE_LONG, CLOSE_ALLは有効
            return signal in [Signal.SELL, Signal.CLOSE_LONG, Signal.CLOSE_ALL]
        
        # ショートポジションがある場合
        if current_position.get('side') == 'SHORT':
            # 追加のSELLシグナルは無効（ドテンなし）
            if signal == Signal.SELL:
                return False
            # BUY, CLOSE_SHORT, CLOSE_ALLは有効
            return signal in [Signal.BUY, Signal.CLOSE_SHORT, Signal.CLOSE_ALL]
        
        return True
    
    def check_entry_conditions(self, df: pd.DataFrame) -> Tuple[bool, Signal, Dict[str, Any]]:
        """
        エントリー条件をチェックする（サブクラスでオーバーライド）
        
        Args:
            df: データフレーム
        
        Returns:
            (条件を満たすか, シグナル, 詳細情報)のタプル
        """
        return False, Signal.HOLD, {}
    
    def check_exit_conditions(self, df: pd.DataFrame, current_position: Dict[str, Any]) -> Tuple[bool, Signal, Dict[str, Any]]:
        """
        エグジット条件をチェックする（サブクラスでオーバーライド）
        
        Args:
            df: データフレーム
            current_position: 現在のポジション情報
        
        Returns:
            (条件を満たすか, シグナル, 詳細情報)のタプル
        """
        return False, Signal.HOLD, {}
    
    def calculate_confidence(self, df: pd.DataFrame, signal: Signal) -> float:
        """
        シグナルの確信度を計算する（0.0〜1.0）
        
        Args:
            df: データフレーム
            signal: シグナル
        
        Returns:
            確信度
        """
        # デフォルトでは固定値を返す
        return 0.7
    
    def get_recommended_stop_loss(self, df: pd.DataFrame, signal: Signal) -> Optional[float]:
        """
        推奨ストップロス価格を取得する
        
        Args:
            df: データフレーム
            signal: シグナル
        
        Returns:
            ストップロス価格（Noneの場合はリスク管理モジュールのデフォルト設定を使用）
        """
        return None
    
    def get_recommended_take_profit(self, df: pd.DataFrame, signal: Signal) -> Optional[float]:
        """
        推奨テイクプロフィット価格を取得する
        
        Args:
            df: データフレーム
            signal: シグナル
        
        Returns:
            テイクプロフィット価格（Noneの場合はリスク管理モジュールのデフォルト設定を使用）
        """
        return None
