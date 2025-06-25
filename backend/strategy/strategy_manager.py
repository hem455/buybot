"""
戦略管理モジュール

利用可能な戦略を管理し、動的に切り替えるためのモジュール。
"""

from typing import Dict, Any, Optional, List, Type
import importlib
import inspect
import json
from datetime import datetime
import threading

from .base_strategy import BaseStrategy, Signal
from .ma_cross_strategy import SimpleMovingAverageCrossStrategy
from .macd_rsi_strategy import MACDRSIStrategy
from .grid_trading_strategy import GridTradingStrategy
from .ml_based_strategy import MLBasedStrategy
from ..config_manager import get_config_manager
from ..logger import get_logger


class StrategyPerformance:
    """戦略パフォーマンス追跡クラス"""
    
    def __init__(self, strategy_id: str):
        self.strategy_id = strategy_id
        self.total_trades = 0
        self.winning_trades = 0
        self.total_return = 0.0
        self.total_pnl = 0.0
        self.max_drawdown = 0.0
        self.current_drawdown = 0.0
        self.last_signal = None
        self.last_signal_time = None
        self.start_time = datetime.now()
        self.error_count = 0
        
    def add_trade(self, pnl: float, winning: bool = None):
        """取引結果を追加"""
        self.total_trades += 1
        self.total_pnl += pnl
        
        if winning is None:
            winning = pnl > 0
            
        if winning:
            self.winning_trades += 1
    
    def update_signal(self, signal: Signal, details: Dict[str, Any]):
        """最新シグナルを更新"""
        self.last_signal = signal
        self.last_signal_time = datetime.now()
    
    def add_error(self):
        """エラーカウントを増加"""
        self.error_count += 1
    
    @property
    def win_rate(self) -> float:
        """勝率を計算"""
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades
    
    @property
    def average_return(self) -> float:
        """平均リターンを計算"""
        if self.total_trades == 0:
            return 0.0
        return self.total_pnl / self.total_trades
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式で情報を返す"""
        return {
            'strategy_id': self.strategy_id,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': self.win_rate,
            'total_pnl': self.total_pnl,
            'average_return': self.average_return,
            'max_drawdown': self.max_drawdown,
            'current_drawdown': self.current_drawdown,
            'last_signal': self.last_signal.value if self.last_signal else None,
            'last_signal_time': self.last_signal_time.isoformat() if self.last_signal_time else None,
            'start_time': self.start_time.isoformat(),
            'error_count': self.error_count,
            'uptime_hours': (datetime.now() - self.start_time).total_seconds() / 3600
        }


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
            'grid_trading': GridTradingStrategy,
            'ml_based': MLBasedStrategy,
        }
        
        # アクティブな戦略とその状態
        self.active_strategies: Dict[str, BaseStrategy] = {}
        self.strategy_states: Dict[str, str] = {}  # 'active', 'paused', 'stopped', 'error'
        self.strategy_performances: Dict[str, StrategyPerformance] = {}
        
        # スレッドセーフ用のロック
        self._lock = threading.RLock()
    
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
            
            # パフォーマンス情報を追加
            performance = self.strategy_performances.get(strategy_id)
            performance_data = performance.to_dict() if performance else {}
            
            strategies.append({
                'id': strategy_id,
                'name': config.get('name', strategy_id),
                'description': config.get('description', ''),
                'parameters': config.get('parameters', {}),
                'class': strategy_class.__name__,
                'state': self.strategy_states.get(strategy_id, 'stopped'),
                'performance': performance_data
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
        
        # デフォルトパラメータを取得
        default_params = self.config.get(f'strategies.available.{strategy_id}.parameters', {})
        
        # パラメータをマージ
        final_params = {**default_params, **(params or {})}
        
        strategy_class = self.available_strategies[strategy_id]
        
        # 戦略クラスの__init__シグネチャを検査
        import inspect
        init_signature = inspect.signature(strategy_class.__init__)
        params_list = list(init_signature.parameters.keys())
        
        # 'self'を除いた引数の数で判定
        if len(params_list) == 2:  # self, params
            strategy = strategy_class(final_params)
        elif len(params_list) >= 3:  # self, strategy_id, params
            strategy = strategy_class(strategy_id, final_params)
        else:
            # フォールバック: パラメータなしで初期化
            strategy = strategy_class()
        
        self.logger.info(f"戦略をロードしました: {strategy_id} with params: {final_params}")
        return strategy
    
    def start_strategy(self, strategy_id: str, params: Optional[Dict[str, Any]] = None) -> bool:
        """
        戦略を開始する
        
        Args:
            strategy_id: 戦略ID
            params: 戦略パラメータ
        
        Returns:
            成功したかどうか
        """
        with self._lock:
            try:
                strategy = self.load_strategy(strategy_id, params)
                self.active_strategies[strategy_id] = strategy
                self.strategy_states[strategy_id] = 'active'
                
                # パフォーマンス追跡を開始
                if strategy_id not in self.strategy_performances:
                    self.strategy_performances[strategy_id] = StrategyPerformance(strategy_id)
                
                self.logger.info(f"戦略を開始しました: {strategy_id}")
                return True
                
            except Exception as e:
                self.logger.error(f"戦略の開始に失敗しました: {strategy_id}, error: {e}")
                self.strategy_states[strategy_id] = 'error'
                return False
    
    def stop_strategy(self, strategy_id: str) -> bool:
        """
        戦略を停止する
        
        Args:
            strategy_id: 戦略ID
        
        Returns:
            成功したかどうか
        """
        with self._lock:
            try:
                if strategy_id in self.active_strategies:
                    del self.active_strategies[strategy_id]
                
                self.strategy_states[strategy_id] = 'stopped'
                self.logger.info(f"戦略を停止しました: {strategy_id}")
                return True
                
            except Exception as e:
                self.logger.error(f"戦略の停止に失敗しました: {strategy_id}, error: {e}")
                return False
    
    def pause_strategy(self, strategy_id: str) -> bool:
        """
        戦略を一時停止する
        
        Args:
            strategy_id: 戦略ID
        
        Returns:
            成功したかどうか
        """
        with self._lock:
            if strategy_id in self.active_strategies:
                self.strategy_states[strategy_id] = 'paused'
                self.logger.info(f"戦略を一時停止しました: {strategy_id}")
                return True
            return False
    
    def resume_strategy(self, strategy_id: str) -> bool:
        """
        戦略を再開する
        
        Args:
            strategy_id: 戦略ID
        
        Returns:
            成功したかどうか
        """
        with self._lock:
            if strategy_id in self.active_strategies and self.strategy_states.get(strategy_id) == 'paused':
                self.strategy_states[strategy_id] = 'active'
                self.logger.info(f"戦略を再開しました: {strategy_id}")
                return True
            return False
    
    def update_strategy_parameters(self, strategy_id: str, new_params: Dict[str, Any]) -> bool:
        """
        稼働中の戦略のパラメータを更新する
        
        Args:
            strategy_id: 戦略ID
            new_params: 新しいパラメータ
        
        Returns:
            成功したかどうか
        """
        with self._lock:
            try:
                if strategy_id in self.active_strategies:
                    # 戦略を一旦停止して再起動
                    current_state = self.strategy_states.get(strategy_id, 'stopped')
                    
                    # パラメータを設定ファイルに反映（オプション）
                    # self.config.update(f'strategies.available.{strategy_id}.parameters', new_params)
                    
                    # 戦略を再起動
                    if current_state == 'active':
                        success = self.start_strategy(strategy_id, new_params)
                        if success:
                            self.logger.info(f"戦略パラメータを更新しました: {strategy_id}, params: {new_params}")
                        return success
                    else:
                        # 停止中の場合はパラメータのみ保存
                        self.logger.info(f"戦略パラメータを保存しました: {strategy_id}, params: {new_params}")
                        return True
                else:
                    self.logger.warning(f"アクティブでない戦略のパラメータ更新: {strategy_id}")
                    return False
                    
            except Exception as e:
                self.logger.error(f"戦略パラメータの更新に失敗しました: {strategy_id}, error: {e}")
                return False
    
    def get_active_strategies(self) -> Dict[str, BaseStrategy]:
        """アクティブな戦略を取得する"""
        with self._lock:
            return {k: v for k, v in self.active_strategies.items() 
                   if self.strategy_states.get(k) == 'active'}
    
    def get_strategy_state(self, strategy_id: str) -> str:
        """戦略の状態を取得する"""
        return self.strategy_states.get(strategy_id, 'stopped')
    
    def get_strategy_performance(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """戦略のパフォーマンスを取得する"""
        performance = self.strategy_performances.get(strategy_id)
        return performance.to_dict() if performance else None
    
    def get_all_strategies_status(self) -> List[Dict[str, Any]]:
        """全戦略の状態とパフォーマンスを取得する"""
        strategies = self.get_available_strategies()
        
        for strategy in strategies:
            strategy_id = strategy['id']
            strategy['state'] = self.get_strategy_state(strategy_id)
            strategy['performance'] = self.get_strategy_performance(strategy_id) or {}
            
            # リアルタイム情報を追加
            if strategy_id in self.active_strategies:
                active_strategy = self.active_strategies[strategy_id]
                strategy['current_params'] = active_strategy.params
            
        return strategies
    
    def record_signal(self, strategy_id: str, signal: Signal, details: Dict[str, Any]):
        """戦略のシグナルを記録する"""
        if strategy_id in self.strategy_performances:
            self.strategy_performances[strategy_id].update_signal(signal, details)
    
    def record_trade(self, strategy_id: str, pnl: float, winning: bool = None):
        """戦略の取引結果を記録する"""
        if strategy_id in self.strategy_performances:
            self.strategy_performances[strategy_id].add_trade(pnl, winning)
    
    def record_error(self, strategy_id: str):
        """戦略のエラーを記録する"""
        if strategy_id in self.strategy_performances:
            self.strategy_performances[strategy_id].add_error()
        
        # エラー状態に設定
        self.strategy_states[strategy_id] = 'error'
    
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
