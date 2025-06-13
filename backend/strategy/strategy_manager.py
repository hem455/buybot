"""
戦略管理モジュール

利用可能な戦略を管理し、動的に切り替えるためのモジュール。
"""

from typing import Dict, Any, Optional, List, Type
import importlib
import inspect

from .base_strategy import BaseStrategy, Signal
from .ma_cross_strategy import SimpleMovingAverageCrossStrategy
from .macd_rsi_strategy import MACDRSIStrategy
from ..config_manager import get_config_manager
from ..logger import get_logger


class StrategyManager:
    """戦略管理クラス"""
    
    def __init__(self):
        """初期化"""
        self.config = get_config_manager()
        self.logger = get_logger()
        
        # 利用可能な戦略を登録
        self.available_strategies: Dict[str, Type[BaseStrategy]] = {
            'simple_ma_cross': SimpleMovingAverageCrossStrategy,
            'macd_rsi': MACDRSIStrategy,
        }
        
        # アクティブな戦略
        self.active_strategy: Optional[BaseStrategy] = None
        self.active_strategy_id: Optional[str] = None
    
    def get_available_strategies(self) -> List[Dict[str, Any]]:
        """
        利用可能な戦略のリストを取得する
        
        Returns:
            戦略情報のリスト
        """
        strategies = []
        available_configs = self.config.get('strategies.available', {})
        
        for strategy_id, strategy_class in self.available_strategies.items():
            config = available_configs.get(strategy_id, {})
            strategies.append({
                'id': strategy_id,
                'name': config.get('name', strategy_id),
                'description': config.get('description', ''),
                'parameters': config.get('parameters', {}),
                'class': strategy_class.__name__
            })
        
        return strategies
    
    def load_strategy(self, strategy_id: str, params: Optional[Dict[str, Any]] = None) -> BaseStrategy:
        """
        戦略をロードする
        
        Args:
            strategy_id: 戦略ID
            params: 戦略パラメータ（省略時は設定から取得）
        
        Returns:
            戦略インスタンス
        """
        if strategy_id not in self.available_strategies:
            raise ValueError(f"利用できない戦略ID: {strategy_id}")
        
        strategy_class = self.available_strategies[strategy_id]
        strategy = strategy_class(params)
        
        self.logger.info(f"戦略をロードしました: {strategy_id}")
        return strategy
    
    def set_active_strategy(self, strategy_id: str, params: Optional[Dict[str, Any]] = None) -> None:
        """
        アクティブな戦略を設定する
        
        Args:
            strategy_id: 戦略ID
            params: 戦略パラメータ
        """
        self.active_strategy = self.load_strategy(strategy_id, params)
        self.active_strategy_id = strategy_id
        self.logger.info(f"アクティブな戦略を設定しました: {strategy_id}")
    
    def get_active_strategy(self) -> Optional[BaseStrategy]:
        """
        アクティブな戦略を取得する
        
        Returns:
            戦略インスタンス
        """
        if self.active_strategy is None:
            # デフォルト戦略をロード
            default_strategy_id = self.config.get('strategies.default', 'simple_ma_cross')
            self.set_active_strategy(default_strategy_id)
        
        return self.active_strategy
    
    def get_active_strategy_info(self) -> Dict[str, Any]:
        """
        アクティブな戦略の情報を取得する
        
        Returns:
            戦略情報
        """
        if self.active_strategy is None:
            return {}
        
        return {
            'id': self.active_strategy_id,
            'name': self.active_strategy.name,
            'description': self.active_strategy.description,
            'parameters': self.active_strategy.params
        }
    
    def register_custom_strategy(self, strategy_id: str, strategy_class: Type[BaseStrategy]) -> None:
        """
        カスタム戦略を登録する
        
        Args:
            strategy_id: 戦略ID
            strategy_class: 戦略クラス
        """
        if not issubclass(strategy_class, BaseStrategy):
            raise ValueError("戦略クラスはBaseStrategyを継承する必要があります")
        
        self.available_strategies[strategy_id] = strategy_class
        self.logger.info(f"カスタム戦略を登録しました: {strategy_id}")
    
    def load_custom_strategy_from_file(self, strategy_id: str, file_path: str, 
                                     class_name: str) -> None:
        """
        ファイルからカスタム戦略をロードして登録する
        
        Args:
            strategy_id: 戦略ID
            file_path: Pythonファイルのパス
            class_name: クラス名
        """
        try:
            # モジュールを動的にインポート
            spec = importlib.util.spec_from_file_location(strategy_id, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # クラスを取得
            if hasattr(module, class_name):
                strategy_class = getattr(module, class_name)
                self.register_custom_strategy(strategy_id, strategy_class)
            else:
                raise ValueError(f"クラス {class_name} が見つかりません")
                
        except Exception as e:
            self.logger.error(f"カスタム戦略のロードに失敗しました: {e}")
            raise


# シングルトンインスタンス
_strategy_manager: Optional[StrategyManager] = None


def get_strategy_manager() -> StrategyManager:
    """StrategyManagerのシングルトンインスタンスを取得する"""
    global _strategy_manager
    if _strategy_manager is None:
        _strategy_manager = StrategyManager()
    return _strategy_manager
