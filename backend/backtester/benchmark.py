"""
ベンチマーク比較モジュール

Buy & Hold戦略との比較を行うモジュール
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple
from datetime import datetime


class BenchmarkComparator:
    """ベンチマーク比較クラス"""
    
    def __init__(self):
        """初期化"""
        self.initial_capital = 1000000  # デフォルト100万円
    
    def calculate_buy_and_hold(self, df: pd.DataFrame, 
                              initial_capital: float,
                              commission_rate: float = 0.0009) -> Dict[str, Any]:
        """
        Buy & Hold戦略の結果を計算
        
        Args:
            df: OHLCVデータ
            initial_capital: 初期資金
            commission_rate: 手数料率
        
        Returns:
            Buy & Hold戦略の結果
        """
        if df.empty:
            return {}
        
        # 開始価格と終了価格
        start_price = df['close'].iloc[0]
        end_price = df['close'].iloc[-1]
        
        # 購入可能なBTC数（手数料考慮）
        btc_amount = (initial_capital * (1 - commission_rate)) / start_price
        
        # 最終価値（売却手数料考慮）
        final_value = btc_amount * end_price * (1 - commission_rate)
        
        # パフォーマンス計算
        total_return = final_value - initial_capital
        total_return_pct = (total_return / initial_capital) * 100
        
        # 最大ドローダウン計算
        prices = df['close'].values
        peak_price = prices[0]
        max_dd = 0
        max_dd_duration = 0
        current_dd_duration = 0
        
        for price in prices:
            if price > peak_price:
                peak_price = price
                current_dd_duration = 0
            else:
                dd = (peak_price - price) / peak_price
                max_dd = max(max_dd, dd)
                current_dd_duration += 1
                max_dd_duration = max(max_dd_duration, current_dd_duration)
        
        # シャープレシオ計算
        returns = df['close'].pct_change().dropna()
        sharpe_ratio = np.sqrt(252) * returns.mean() / returns.std() if returns.std() > 0 else 0
        
        return {
            'initial_capital': initial_capital,
            'final_value': final_value,
            'total_return': total_return,
            'total_return_pct': total_return_pct,
            'max_drawdown_pct': max_dd * 100,
            'max_drawdown_duration_hours': max_dd_duration,
            'sharpe_ratio': sharpe_ratio,
            'btc_amount': btc_amount,
            'start_price': start_price,
            'end_price': end_price
        }
    
    def compare_with_strategy(self, strategy_result: Dict[str, Any],
                            buy_hold_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        戦略とBuy & Holdを比較
        
        Args:
            strategy_result: 戦略のバックテスト結果
            buy_hold_result: Buy & Holdの結果
        
        Returns:
            比較結果
        """
        strategy_summary = strategy_result.get('summary', {})
        
        # パフォーマンス差分
        return_diff = strategy_summary.get('total_return_pct', 0) - buy_hold_result.get('total_return_pct', 0)
        sharpe_diff = strategy_summary.get('sharpe_ratio', 0) - buy_hold_result.get('sharpe_ratio', 0)
        dd_diff = strategy_summary.get('max_drawdown_pct', 0) - buy_hold_result.get('max_drawdown_pct', 0)
        
        # アウトパフォーム判定
        outperforms = return_diff > 0 and sharpe_diff > 0
        
        return {
            'strategy_beats_buy_hold': outperforms,
            'return_difference_pct': return_diff,
            'sharpe_ratio_difference': sharpe_diff,
            'drawdown_difference_pct': dd_diff,
            'strategy': {
                'total_return_pct': strategy_summary.get('total_return_pct', 0),
                'sharpe_ratio': strategy_summary.get('sharpe_ratio', 0),
                'max_drawdown_pct': strategy_summary.get('max_drawdown_pct', 0),
                'total_trades': strategy_summary.get('total_trades', 0),
                'win_rate': strategy_summary.get('win_rate', 0)
            },
            'buy_and_hold': {
                'total_return_pct': buy_hold_result.get('total_return_pct', 0),
                'sharpe_ratio': buy_hold_result.get('sharpe_ratio', 0),
                'max_drawdown_pct': buy_hold_result.get('max_drawdown_pct', 0)
            }
        }
    
    def calculate_risk_metrics(self, equity_curve: pd.DataFrame) -> Dict[str, Any]:
        """
        詳細なリスクメトリクスを計算
        
        Args:
            equity_curve: 資産推移データ
        
        Returns:
            リスクメトリクス
        """
        if equity_curve.empty:
            return {}
        
        # 日次リターン計算
        returns = equity_curve['equity'].pct_change().dropna()
        
        # ソルティノレシオ（下方リスクのみ考慮）
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std() if len(downside_returns) > 0 else 0
        sortino_ratio = np.sqrt(252) * returns.mean() / downside_std if downside_std > 0 else 0
        
        # カルマーレシオ（リターン/最大DD）
        max_dd = self._calculate_max_drawdown(equity_curve['equity'])
        annual_return = (equity_curve['equity'].iloc[-1] / equity_curve['equity'].iloc[0]) ** (365 / len(equity_curve)) - 1
        calmar_ratio = annual_return / abs(max_dd) if max_dd != 0 else 0
        
        # 最大ドローダウン期間
        dd_periods = self._calculate_drawdown_periods(equity_curve['equity'])
        
        return {
            'sortino_ratio': sortino_ratio,
            'calmar_ratio': calmar_ratio,
            'max_consecutive_losses': self._calculate_max_consecutive_losses(returns),
            'recovery_periods': dd_periods,
            'value_at_risk_95': np.percentile(returns, 5) if len(returns) > 0 else 0
        }
    
    def _calculate_max_drawdown(self, equity_series: pd.Series) -> float:
        """最大ドローダウンを計算"""
        peak = equity_series.expanding().max()
        dd = (equity_series - peak) / peak
        return dd.min()
    
    def _calculate_drawdown_periods(self, equity_series: pd.Series) -> Dict[str, int]:
        """ドローダウン期間を計算"""
        peak = equity_series.expanding().max()
        dd = equity_series < peak
        
        # 最大ドローダウン期間
        max_period = 0
        current_period = 0
        
        for is_dd in dd:
            if is_dd:
                current_period += 1
                max_period = max(max_period, current_period)
            else:
                current_period = 0
        
        return {
            'max_drawdown_period': max_period,
            'current_drawdown_period': current_period
        }
    
    def _calculate_max_consecutive_losses(self, returns: pd.Series) -> int:
        """最大連続損失数を計算"""
        max_losses = 0
        current_losses = 0
        
        for ret in returns:
            if ret < 0:
                current_losses += 1
                max_losses = max(max_losses, current_losses)
            else:
                current_losses = 0
        
        return max_losses
