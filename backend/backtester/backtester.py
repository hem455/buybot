"""
バックテストモジュール

ヒストリカルデータを使用して戦略のパフォーマンスを検証するモジュール。
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import json

from ..config_manager import get_config_manager
from ..logger import get_logger
from ..data_fetcher import DataStorage
from ..indicator import IndicatorCalculator
from ..strategy import BaseStrategy, Signal, get_strategy_manager
from ..risk_manager import RiskManager


class Backtester:
    """バックテストクラス"""
    
    def __init__(self):
        """初期化"""
        self.config = get_config_manager()
        self.logger = get_logger()
        self.backtest_config = self.config.get('backtest', {})
        
        # コンポーネント
        self.data_storage = DataStorage(self.config)
        self.indicator_calculator = IndicatorCalculator()
        self.strategy_manager = get_strategy_manager()
        self.risk_manager = RiskManager()
        
        # バックテスト設定
        self.initial_capital = self.backtest_config.get('initial_capital', 1000000)
        self.commission_config = self.backtest_config.get('commission', {})
        self.slippage_config = self.backtest_config.get('slippage', {})
        
        # 結果格納用
        self.trades: List[Dict[str, Any]] = []
        self.equity_curve: List[Dict[str, Any]] = []
        self.positions: List[Dict[str, Any]] = []
        self.signals: List[Dict[str, Any]] = []
    
    def run_backtest(self, strategy_id: str, start_date: datetime, end_date: datetime,
                    symbol: str = None, interval: str = '1hour',
                    parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        バックテストを実行する
        
        Args:
            strategy_id: 戦略ID
            start_date: 開始日
            end_date: 終了日
            symbol: 通貨ペア（省略時は設定から取得）
            interval: 時間間隔
            parameters: 戦略パラメータ
        
        Returns:
            バックテスト結果
        """
        self.logger.info(f"バックテスト開始: {strategy_id} ({start_date} - {end_date})")
        
        # 初期化
        self._reset()
        
        # シンボルを取得
        if symbol is None:
            symbol = self.config.get('trading.symbol', 'BTC_JPY')
        
        # データを読み込む
        df = self.data_storage.load_ohlcv(symbol, interval, start_date, end_date)
        if df.empty:
            error_msg = f"OHLCVデータが読めずバックテストを中止しました（symbol={symbol}, interval={interval}）"
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        # 指標を計算（戦略パラメータを考慮）
        df = self.indicator_calculator.calculate_dynamic_indicators(df, parameters)
        
        # 戦略固有の指標を追加計算（simple_ma_crossの場合）
        if strategy_id == 'simple_ma_cross':
            if parameters:
                short_period = parameters.get('short_period', 5)
                long_period = parameters.get('long_period', 20)
                df = self.indicator_calculator.add_sma(df, [short_period, long_period])
        
        # 戦略をロード
        strategy = self.strategy_manager.load_strategy(strategy_id, parameters)
        
        # 現在の状態
        account_balance = self.initial_capital
        position = None
        
        # 各バーでシミュレーション
        for i in range(len(df)):
            current_bar = df.iloc[i]
            current_time = df.index[i]  # timestampはインデックスになっている
            current_price = current_bar['close']
            
            # 現在のデータフレーム（i+1までのデータ）
            current_df = df.iloc[:i+1]
            
            # 口座情報
            account_info = {
                'total_balance': account_balance,
                'available_balance': account_balance if position is None else 0,
                'margin_level': 1.0
            }
            
            # シグナルを生成
            signal, signal_details = strategy.generate_signal(
                current_df,
                position,
                account_info
            )
            
            # シグナルを記録
            if signal != Signal.HOLD:
                self.signals.append({
                    'timestamp': current_time,
                    'signal': signal.value,
                    'price': current_price,
                    'details': signal_details
                })
            
            # シグナルに基づいて取引を実行
            if signal != Signal.HOLD:
                trade_result = self._execute_trade(
                    signal,
                    current_price,
                    current_time,
                    account_balance,
                    position,
                    strategy,
                    current_df
                )
                
                if trade_result['executed']:
                    # 取引を記録
                    self.trades.append(trade_result['trade'])
                    
                    # ポジションを更新
                    if trade_result['position_closed']:
                        position = None
                    
                    if trade_result['position_opened']:
                        position = trade_result['new_position']
                    
                    # 残高を更新
                    account_balance = trade_result['new_balance']
            
            # 含み損益を計算
            unrealized_pnl = 0
            if position:
                if position['side'] == 'LONG':
                    unrealized_pnl = (current_price - position['entry_price']) * position['size']
                else:  # SHORT
                    unrealized_pnl = (position['entry_price'] - current_price) * position['size']
            
            # 資産推移を記録
            self.equity_curve.append({
                'timestamp': current_time,
                'balance': account_balance,
                'equity': account_balance + unrealized_pnl,
                'price': current_price
            })
        
        # 最終的なポジションをクローズ
        if position:
            final_bar = df.iloc[-1]
            close_result = self._close_position(
                position,
                final_bar['close'],
                df.index[-1],  # timestampはインデックスになっている
                account_balance
            )
            
            if close_result['executed']:
                self.trades.append(close_result['trade'])
                account_balance = close_result['new_balance']
        
        # Buy & Hold戦略の結果を計算
        buy_hold_result = None
        if not df.empty:
            from .benchmark import BenchmarkComparator
            comparator = BenchmarkComparator()
            buy_hold_result = comparator.calculate_buy_and_hold(
                df, 
                self.initial_capital,
                self.commission_config.get('taker_fee', 0.0009)
            )
        
        # 結果を生成
        result = self._generate_result(strategy_id, start_date, end_date, symbol, interval)
        if buy_hold_result:
            result['buy_hold_comparison'] = buy_hold_result
        return result
    
    def _reset(self) -> None:
        """バックテスト状態をリセット"""
        self.trades = []
        self.equity_curve = []
        self.positions = []
        self.signals = []
    
    def _execute_trade(self, signal: Signal, price: float, timestamp: datetime,
                      balance: float, current_position: Optional[Dict[str, Any]],
                      strategy: BaseStrategy, df: pd.DataFrame) -> Dict[str, Any]:
        """
        取引を実行する
        
        Returns:
            取引結果
        """
        result = {
            'executed': False,
            'trade': None,
            'position_opened': False,
            'position_closed': False,
            'new_position': None,
            'new_balance': balance
        }
        
        # エントリーシグナルの場合
        if signal in [Signal.BUY, Signal.SELL]:
            # ポジションサイズを計算
            atr = df['atr'].iloc[-1] if 'atr' in df.columns else None
            stop_loss = self.risk_manager.calculate_stop_loss(signal, price, atr)
            position_size = self.risk_manager.calculate_position_size(
                signal, balance, price, stop_loss
            )
            
            if position_size > 0:
                # スリッページを適用
                entry_price = self._apply_slippage(price, signal)
                
                # 手数料を計算
                commission = self._calculate_commission(position_size * entry_price, True)
                
                # 取引を記録
                trade = {
                    'timestamp': timestamp,
                    'type': 'ENTRY',
                    'side': 'BUY' if signal == Signal.BUY else 'SELL',
                    'price': entry_price,
                    'size': position_size,
                    'value': position_size * entry_price,
                    'commission': commission,
                    'balance_before': balance,
                    'balance_after': balance - commission
                }
                
                # 新しいポジション
                new_position = {
                    'side': 'LONG' if signal == Signal.BUY else 'SHORT',
                    'entry_price': entry_price,
                    'size': position_size,
                    'entry_time': timestamp,
                    'stop_loss': stop_loss,
                    'take_profit': self.risk_manager.calculate_take_profit(signal, entry_price, stop_loss)
                }
                
                result['executed'] = True
                result['trade'] = trade
                result['position_opened'] = True
                result['new_position'] = new_position
                result['new_balance'] = balance - commission
        
        # エグジットシグナルの場合
        elif signal in [Signal.CLOSE_LONG, Signal.CLOSE_SHORT, Signal.CLOSE_ALL] and current_position:
            close_result = self._close_position(current_position, price, timestamp, balance)
            result.update(close_result)
        
        return result
    
    def _close_position(self, position: Dict[str, Any], price: float,
                       timestamp: datetime, balance: float) -> Dict[str, Any]:
        """
        ポジションをクローズする
        
        Returns:
            クローズ結果
        """
        # スリッページを適用
        exit_signal = Signal.SELL if position['side'] == 'LONG' else Signal.BUY
        exit_price = self._apply_slippage(price, exit_signal)
        
        # 損益を計算
        if position['side'] == 'LONG':
            pnl = (exit_price - position['entry_price']) * position['size']
        else:  # SHORT
            pnl = (position['entry_price'] - exit_price) * position['size']
        
        # 手数料を計算
        commission = self._calculate_commission(position['size'] * exit_price, False)
        
        # 取引を記録
        trade = {
            'timestamp': timestamp,
            'type': 'EXIT',
            'side': 'SELL' if position['side'] == 'LONG' else 'BUY',
            'price': exit_price,
            'size': position['size'],
            'value': position['size'] * exit_price,
            'commission': commission,
            'pnl': pnl,
            'balance_before': balance,
            'balance_after': balance + pnl - commission
        }
        
        return {
            'executed': True,
            'trade': trade,
            'position_closed': True,
            'new_balance': balance + pnl - commission
        }
    
    def _apply_slippage(self, price: float, signal: Signal) -> float:
        """スリッページを適用する"""
        if not self.slippage_config.get('enabled', True):
            return price
        
        slippage_type = self.slippage_config.get('type', 'percentage')
        
        if slippage_type == 'percentage':
            slippage_pct = self.slippage_config.get('percentage', 0.0001)
            if signal in [Signal.BUY, Signal.CLOSE_SHORT]:
                # 買いの場合は不利な方向（高く）
                return price * (1 + slippage_pct)
            else:
                # 売りの場合は不利な方向（安く）
                return price * (1 - slippage_pct)
        
        elif slippage_type == 'fixed':
            slippage_amount = self.slippage_config.get('amount', 100)
            if signal in [Signal.BUY, Signal.CLOSE_SHORT]:
                return price + slippage_amount
            else:
                return price - slippage_amount
        
        return price
    
    def _calculate_commission(self, value: float, is_maker: bool) -> float:
        """手数料を計算する"""
        commission_type = self.commission_config.get('type', 'percentage')
        
        if commission_type == 'percentage':
            if is_maker:
                rate = self.commission_config.get('maker_fee', 0.0005)
            else:
                rate = self.commission_config.get('taker_fee', 0.0009)
            return value * rate
        
        elif commission_type == 'fixed':
            return self.commission_config.get('fixed_fee', 0)
        
        return 0
    
    def _generate_result(self, strategy_id: str, start_date: datetime, 
                        end_date: datetime, symbol: str, interval: str) -> Dict[str, Any]:
        """バックテスト結果を生成する"""
        # トレード統計を計算
        stats = self._calculate_statistics()
        
        # 資産曲線データを準備
        equity_df = pd.DataFrame(self.equity_curve)
        if not equity_df.empty:
            equity_data = {
                'timestamps': equity_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
                'balance': equity_df['balance'].tolist(),
                'equity': equity_df['equity'].tolist()
            }
        else:
            equity_data = {
                'timestamps': [],
                'balance': [],
                'equity': []
            }
        
        # 取引履歴を準備
        trades_data = []
        for trade in self.trades:
            trade_copy = trade.copy()
            if isinstance(trade_copy['timestamp'], datetime):
                trade_copy['timestamp'] = trade_copy['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
            trades_data.append(trade_copy)
        
        return {
            'summary': {
                'strategy_id': strategy_id,
                'symbol': symbol,
                'interval': interval,
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'initial_capital': self.initial_capital,
                'final_balance': stats['final_balance'],
                'total_return': stats['total_return'],
                'total_return_pct': stats['total_return_pct'],
                'total_trades': stats['total_trades'],
                'winning_trades': stats['winning_trades'],
                'losing_trades': stats['losing_trades'],
                'win_rate': stats['win_rate'],
                'profit_factor': stats['profit_factor'],
                'max_drawdown': stats['max_drawdown'],
                'max_drawdown_pct': stats['max_drawdown_pct'],
                'sharpe_ratio': stats['sharpe_ratio'],
                'average_win': stats['average_win'],
                'average_loss': stats['average_loss'],
                'largest_win': stats['largest_win'],
                'largest_loss': stats['largest_loss'],
                'total_fees': stats['total_fees']
            },
            'equity_curve': equity_data,
            'trades': trades_data,
            'signals': self.signals
        }
    
    def _calculate_statistics(self) -> Dict[str, Any]:
        """統計情報を計算する"""
        if not self.trades:
            return self._empty_statistics()
        
        # トレードデータフレームを作成
        trades_df = pd.DataFrame(self.trades)
        
        # 最終残高
        final_balance = self.initial_capital
        if self.equity_curve:
            final_balance = self.equity_curve[-1]['balance']
        
        # 総リターン
        total_return = final_balance - self.initial_capital
        total_return_pct = (total_return / self.initial_capital) * 100
        
        # 勝敗統計
        exit_trades = trades_df[trades_df['type'] == 'EXIT']
        if not exit_trades.empty:
            winning_trades = exit_trades[exit_trades['pnl'] > 0]
            losing_trades = exit_trades[exit_trades['pnl'] < 0]
            
            total_trades = len(exit_trades)
            win_count = len(winning_trades)
            loss_count = len(losing_trades)
            win_rate = (win_count / total_trades) * 100 if total_trades > 0 else 0
            
            # プロフィットファクター
            total_profit = winning_trades['pnl'].sum() if not winning_trades.empty else 0
            total_loss = abs(losing_trades['pnl'].sum()) if not losing_trades.empty else 0
            profit_factor = total_profit / total_loss if total_loss > 0 else 0
            
            # 平均勝敗
            average_win = winning_trades['pnl'].mean() if not winning_trades.empty else 0
            average_loss = losing_trades['pnl'].mean() if not losing_trades.empty else 0
            
            # 最大勝敗
            largest_win = winning_trades['pnl'].max() if not winning_trades.empty else 0
            largest_loss = losing_trades['pnl'].min() if not losing_trades.empty else 0
        else:
            total_trades = win_count = loss_count = 0
            win_rate = profit_factor = 0
            average_win = average_loss = 0
            largest_win = largest_loss = 0
        
        # 最大ドローダウン
        equity_df = pd.DataFrame(self.equity_curve)
        if not equity_df.empty:
            equity_df['peak'] = equity_df['equity'].cummax()
            equity_df['drawdown'] = equity_df['equity'] - equity_df['peak']
            equity_df['drawdown_pct'] = (equity_df['drawdown'] / equity_df['peak']) * 100
            
            max_drawdown = equity_df['drawdown'].min()
            max_drawdown_pct = equity_df['drawdown_pct'].min()
        else:
            max_drawdown = max_drawdown_pct = 0
        
        # シャープレシオ
        if len(equity_df) > 1:
            equity_df['returns'] = equity_df['equity'].pct_change()
            returns_mean = equity_df['returns'].mean()
            returns_std = equity_df['returns'].std()
            sharpe_ratio = (returns_mean / returns_std) * np.sqrt(252) if returns_std > 0 else 0
        else:
            sharpe_ratio = 0
        
        # 総手数料
        total_fees = trades_df['commission'].sum() if 'commission' in trades_df.columns else 0
        
        return {
            'final_balance': final_balance,
            'total_return': total_return,
            'total_return_pct': total_return_pct,
            'total_trades': total_trades,
            'winning_trades': win_count,
            'losing_trades': loss_count,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': abs(max_drawdown_pct),
            'sharpe_ratio': sharpe_ratio,
            'average_win': average_win,
            'average_loss': average_loss,
            'largest_win': largest_win,
            'largest_loss': largest_loss,
            'total_fees': total_fees
        }
    
    def _empty_statistics(self) -> Dict[str, Any]:
        """空の統計情報を返す"""
        return {
            'final_balance': self.initial_capital,
            'total_return': 0,
            'total_return_pct': 0,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'profit_factor': 0,
            'max_drawdown': 0,
            'max_drawdown_pct': 0,
            'sharpe_ratio': 0,
            'average_win': 0,
            'average_loss': 0,
            'largest_win': 0,
            'largest_loss': 0,
            'total_fees': 0
        }
    
    def _generate_empty_result(self) -> Dict[str, Any]:
        """空の結果を生成する"""
        return {
            'summary': self._empty_statistics(),
            'equity_curve': {
                'timestamps': [],
                'balance': [],
                'equity': []
            },
            'trades': [],
            'signals': []
        }
