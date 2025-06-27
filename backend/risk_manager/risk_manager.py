"""
リスク管理モジュール

ポジションサイジング、リスク管理、資金管理を行うモジュール。
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import pandas as pd
import numpy as np
import numpy as np

from ..config_manager import get_config_manager
from ..logger import get_logger
from ..strategy import Signal


class RiskManager:
    """リスク管理クラス"""
    
    def __init__(self):
        """初期化"""
        self.config = get_config_manager()
        self.logger = get_logger()
        self.risk_config = self.config.get_risk_config()
        self.trading_config = self.config.get_trading_config()
        
        # 取引履歴
        self.trade_history: List[Dict[str, Any]] = []
        self.daily_trades = 0
        self.last_trade_date = None
        
        # パフォーマンス追跡
        self.peak_balance = 0
        self.current_drawdown = 0
    
    def calculate_position_size(self, signal: Signal, account_balance: float, 
                              current_price: float, stop_loss_price: Optional[float] = None) -> float:
        """
        ポジションサイズを計算する
        
        Args:
            signal: シグナル
            account_balance: 口座残高
            current_price: 現在価格
            stop_loss_price: ストップロス価格（オプション）
        
        Returns:
            ポジションサイズ（BTC）
        """
        if signal not in [Signal.BUY, Signal.SELL]:
            return 0.0
        
        # ポジションサイジング設定を取得
        sizing_config = self.risk_config.get('position_sizing', {})
        method = sizing_config.get('method', 'fixed_percentage')
        risk_per_trade = sizing_config.get('risk_per_trade', 0.02)
        max_position_size = sizing_config.get('max_position_size', 0.1)
        
        position_size = 0.0
        
        if method == 'fixed_percentage':
            # 固定パーセンテージ方式
            if stop_loss_price:
                # ストップロスが設定されている場合
                risk_amount = account_balance * risk_per_trade
                price_risk = abs(current_price - stop_loss_price)
                if price_risk > 0:
                    position_size = risk_amount / price_risk
            else:
                # ストップロスが設定されていない場合は総資産の一定割合
                position_value = account_balance * risk_per_trade
                position_size = position_value / current_price
        
        elif method == 'fixed_amount':
            # 固定額方式
            position_size = risk_per_trade  # この場合、risk_per_tradeは固定のBTC数
        
        elif method == 'kelly':
            # ケリー基準（要実装）
            position_size = self._calculate_kelly_size(account_balance, current_price)
        
        # 最大ポジションサイズ制限
        position_size = min(position_size, max_position_size)
        
        # 最小取引サイズチェック
        min_order_size = self.trading_config.get('min_order_size', 0.0001)
        if position_size < min_order_size:
            self.logger.warning(f"計算されたポジションサイズ（{position_size}）が最小サイズ未満です")
            return 0.0
        
        # 小数点以下を調整
        tick_size = 0.0001  # BTCの最小単位
        position_size = round(position_size / tick_size) * tick_size
        
        return position_size
    
    def calculate_stop_loss(self, signal: Signal, entry_price: float, 
                          atr: Optional[float] = None) -> Optional[float]:
        """
        ストップロス価格を計算する
        
        Args:
            signal: シグナル
            entry_price: エントリー価格
            atr: ATR値（オプション）
        
        Returns:
            ストップロス価格
        """
        sl_config = self.risk_config.get('stop_loss', {})
        if not sl_config.get('enabled', True):
            return None
        
        method = sl_config.get('method', 'percentage')
        
        if method == 'percentage':
            # パーセンテージ方式
            percentage = sl_config.get('percentage', 0.02)
            if signal == Signal.BUY:
                stop_loss = entry_price * (1 - percentage)
            else:  # SELL
                stop_loss = entry_price * (1 + percentage)
        
        elif method == 'atr' and atr:
            # ATR方式
            multiplier = sl_config.get('atr_multiplier', 2.0)
            if signal == Signal.BUY:
                stop_loss = entry_price - (atr * multiplier)
            else:  # SELL
                stop_loss = entry_price + (atr * multiplier)
        
        elif method == 'fixed_amount':
            # 固定額方式
            amount = sl_config.get('fixed_amount', 50000)  # 5万円
            if signal == Signal.BUY:
                stop_loss = entry_price - amount
            else:  # SELL
                stop_loss = entry_price + amount
        
        else:
            return None
        
        # NaNチェック
        if pd.isna(stop_loss) or not np.isfinite(stop_loss):
            self.logger.warning(f"ストップロス価格が無効です（NaN）: ATR={atr}")
            return None
        
        # 価格を丸める
        tick_size = self.trading_config.get('tick_size', 1)
        stop_loss = round(stop_loss / tick_size) * tick_size
        
        return stop_loss
    
    def calculate_take_profit(self, signal: Signal, entry_price: float, 
                            stop_loss_price: Optional[float] = None) -> Optional[float]:
        """
        テイクプロフィット価格を計算する
        
        Args:
            signal: シグナル
            entry_price: エントリー価格
            stop_loss_price: ストップロス価格（オプション）
        
        Returns:
            テイクプロフィット価格
        """
        tp_config = self.risk_config.get('take_profit', {})
        if not tp_config.get('enabled', True):
            return None
        
        method = tp_config.get('method', 'risk_reward')
        
        if method == 'risk_reward' and stop_loss_price:
            # リスクリワード比方式
            ratio = tp_config.get('risk_reward_ratio', 2.0)
            risk = abs(entry_price - stop_loss_price)
            if signal == Signal.BUY:
                take_profit = entry_price + (risk * ratio)
            else:  # SELL
                take_profit = entry_price - (risk * ratio)
        
        elif method == 'percentage':
            # パーセンテージ方式
            percentage = tp_config.get('percentage', 0.04)
            if signal == Signal.BUY:
                take_profit = entry_price * (1 + percentage)
            else:  # SELL
                take_profit = entry_price * (1 - percentage)
        
        elif method == 'fixed_amount':
            # 固定額方式
            amount = tp_config.get('fixed_amount', 100000)  # 10万円
            if signal == Signal.BUY:
                take_profit = entry_price + amount
            else:  # SELL
                take_profit = entry_price - amount
        
        else:
            return None
        
        # 価格を丸める
        tick_size = self.trading_config.get('tick_size', 1)
        take_profit = round(take_profit / tick_size) * tick_size
        
        return take_profit
    
    def check_risk_limits(self, account_info: Dict[str, Any], 
                         current_positions: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        リスク制限をチェックする
        
        Args:
            account_info: 口座情報
            current_positions: 現在のポジション
        
        Returns:
            (取引可能か, 理由)のタプル
        """
        # 最大オープンポジション数チェック
        max_positions = self.risk_config.get('max_open_positions', 3)
        if len(current_positions) >= max_positions:
            return False, f"最大ポジション数（{max_positions}）に達しています"
        
        # 日次取引数チェック
        current_date = datetime.now().date()
        if self.last_trade_date != current_date:
            self.daily_trades = 0
            self.last_trade_date = current_date
        
        max_daily_trades = self.risk_config.get('max_daily_trades', 10)
        if self.daily_trades >= max_daily_trades:
            return False, f"日次最大取引数（{max_daily_trades}）に達しています"
        
        # 最大ドローダウンチェック
        current_balance = account_info.get('total_balance', 0)
        if self.peak_balance > 0:
            drawdown = (self.peak_balance - current_balance) / self.peak_balance
            max_drawdown = self.risk_config.get('max_drawdown_percentage', 0.20)
            if drawdown >= max_drawdown:
                return False, f"最大ドローダウン（{max_drawdown * 100}%）に達しています"
        
        # マージンコールチェック
        margin_level = account_info.get('margin_level', 1.0)
        margin_call_level = self.risk_config.get('margin_call_percentage', 0.05)
        if margin_level <= margin_call_level:
            return False, f"マージンレベル（{margin_level * 100}%）が危険水準です"
        
        return True, ""
    
    def update_trade_history(self, trade: Dict[str, Any]) -> None:
        """
        取引履歴を更新する
        
        Args:
            trade: 取引情報
        """
        self.trade_history.append(trade)
        self.daily_trades += 1
        
        # パフォーマンス追跡を更新
        if 'realized_pnl' in trade:
            current_balance = trade.get('balance_after', 0)
            if current_balance > self.peak_balance:
                self.peak_balance = current_balance
                self.current_drawdown = 0
            else:
                self.current_drawdown = (self.peak_balance - current_balance) / self.peak_balance
    
    def calculate_portfolio_metrics(self) -> Dict[str, Any]:
        """
        ポートフォリオメトリクスを計算する
        
        Returns:
            メトリクス辞書
        """
        if not self.trade_history:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'average_win': 0,
                'average_loss': 0
            }
        
        # 取引データを分析
        df = pd.DataFrame(self.trade_history)
        
        # 基本統計
        total_trades = len(df)
        winning_trades = df[df['realized_pnl'] > 0]
        losing_trades = df[df['realized_pnl'] < 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
        
        # 利益率
        total_profit = winning_trades['realized_pnl'].sum() if len(winning_trades) > 0 else 0
        total_loss = abs(losing_trades['realized_pnl'].sum()) if len(losing_trades) > 0 else 0
        profit_factor = total_profit / total_loss if total_loss > 0 else 0
        
        # 平均勝敗
        average_win = winning_trades['realized_pnl'].mean() if len(winning_trades) > 0 else 0
        average_loss = losing_trades['realized_pnl'].mean() if len(losing_trades) > 0 else 0
        
        # シャープレシオ（簡易版）
        if 'returns' in df.columns:
            returns = df['returns']
            sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        else:
            sharpe_ratio = 0
        
        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': self.current_drawdown,
            'average_win': average_win,
            'average_loss': average_loss
        }
    
    def _calculate_kelly_size(self, account_balance: float, current_price: float) -> float:
        """
        ケリー基準でポジションサイズを計算する（要実装）
        
        Args:
            account_balance: 口座残高
            current_price: 現在価格
        
        Returns:
            ポジションサイズ
        """
        # 簡易的な実装
        # 実際にはより詳細な勝率と期待値の計算が必要
        metrics = self.calculate_portfolio_metrics()
        win_rate = metrics['win_rate']
        avg_win = metrics['average_win']
        avg_loss = abs(metrics['average_loss'])
        
        if avg_loss == 0:
            return 0.0
        
        # ケリー比率 = (勝率 * 平均利益 - 敗率 * 平均損失) / 平均利益
        kelly_percentage = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win if avg_win > 0 else 0
        
        # 安全のため25%に制限
        kelly_percentage = min(kelly_percentage, 0.25)
        
        if kelly_percentage <= 0:
            return 0.0
        
        position_value = account_balance * kelly_percentage
        return position_value / current_price
