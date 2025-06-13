"""
ダッシュボード用ヘルパー関数とリアルタイムデータ処理
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import asyncio
from typing import Dict, Any, List, Optional
import json

# バックエンドモジュールのインポート
from backend.data_fetcher import GMOCoinRESTFetcher, GMOCoinWebSocketFetcher
from backend.config_manager import get_config_manager
from backend.logger import get_logger


class DashboardDataManager:
    """ダッシュボードデータ管理クラス"""
    
    def __init__(self):
        self.config = get_config_manager()
        self.logger = get_logger()
        self.rest_fetcher = GMOCoinRESTFetcher()
        self.ws_fetcher = None
        self.latest_prices = {}
        self.portfolio_history = []
        
    async def initialize(self):
        """初期化"""
        self.ws_fetcher = GMOCoinWebSocketFetcher(self.config)
        await self.ws_fetcher.connect()
        
    async def get_account_summary(self) -> Dict[str, Any]:
        """アカウントサマリーを取得"""
        try:
            async with self.rest_fetcher as fetcher:
                # 残高情報
                balance = await fetcher.fetch_balance()
                
                # ポジション情報
                positions = await fetcher.fetch_positions()
                
                # 総資産を計算
                total_jpy = balance.get('JPY', {}).get('amount', 0)
                
                # 各通貨の評価額を加算
                for symbol, data in balance.items():
                    if symbol != 'JPY' and data['amount'] > 0:
                        # 現在価格を取得
                        ticker = await fetcher.fetch_ticker(f"{symbol}_JPY")
                        if ticker:
                            total_jpy += data['amount'] * ticker['last']
                
                # 本日のP/L（仮想データ - 実際は取引履歴から計算）
                today_pnl = np.random.normal(50000, 20000)
                today_pnl_pct = (today_pnl / total_jpy) * 100
                
                return {
                    'total_balance': total_jpy,
                    'today_pnl': today_pnl,
                    'today_pnl_pct': today_pnl_pct,
                    'positions_count': len(positions),
                    'positions': positions
                }
                
        except Exception as e:
            self.logger.error(f"アカウントサマリー取得エラー: {e}")
            # デモデータを返す
            return {
                'total_balance': 1986154,
                'today_pnl': 45678,
                'today_pnl_pct': 2.34,
                'positions_count': 3,
                'positions': []
            }
    
    async def get_market_prices(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """市場価格を取得"""
        prices = {}
        
        try:
            async with self.rest_fetcher as fetcher:
                for symbol in symbols:
                    ticker = await fetcher.fetch_ticker(symbol)
                    if ticker:
                        # 24時間前の価格（仮想）
                        prev_price = ticker['last'] * (1 - np.random.uniform(-0.05, 0.05))
                        change_pct = ((ticker['last'] - prev_price) / prev_price) * 100
                        
                        prices[symbol] = {
                            'last': ticker['last'],
                            'bid': ticker['bid'],
                            'ask': ticker['ask'],
                            'volume': ticker['volume'],
                            'change_24h': change_pct
                        }
                    
                    # レート制限
                    await asyncio.sleep(0.1)
                    
        except Exception as e:
            self.logger.error(f"市場価格取得エラー: {e}")
            # デモデータ
            demo_prices = {
                'BTC_JPY': 6789012,
                'ETH_JPY': 567890,
                'XRP_JPY': 62.10,
                'LTC_JPY': 12345
            }
            
            for symbol in symbols:
                if symbol in demo_prices:
                    base_price = demo_prices[symbol]
                    change = np.random.uniform(-5, 5)
                    prices[symbol] = {
                        'last': base_price,
                        'bid': base_price * 0.999,
                        'ask': base_price * 1.001,
                        'volume': np.random.uniform(100, 1000),
                        'change_24h': change
                    }
        
        return prices
    
    async def get_portfolio_performance(self, days: int = 180) -> pd.DataFrame:
        """ポートフォリオパフォーマンスを取得"""
        try:
            # 実際の取引履歴から計算する場合のロジック
            # ここではデモデータを生成
            dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
            
            # リアルな値動きをシミュレート
            returns = np.random.normal(0.002, 0.02, size=len(dates))
            returns = np.where(returns > 0.05, 0.05, returns)
            returns = np.where(returns < -0.05, -0.05, returns)
            
            # 累積リターン
            cumulative_returns = (1 + returns).cumprod()
            portfolio_value = 1000000 * cumulative_returns
            
            df = pd.DataFrame({
                'date': dates,
                'value': portfolio_value,
                'daily_return': returns,
                'cumulative_return': cumulative_returns - 1
            })
            
            return df
            
        except Exception as e:
            self.logger.error(f"ポートフォリオパフォーマンス取得エラー: {e}")
            return pd.DataFrame()
    
    async def get_strategy_performance(self) -> List[Dict[str, Any]]:
        """戦略別パフォーマンスを取得"""
        strategies = [
            {
                'id': 'grid_trading',
                'name': 'Grid Trading',
                'status': 'Active',
                'total_trades': 156,
                'winning_trades': 106,
                'total_return': 0.234,
                'sharpe_ratio': 1.85,
                'max_drawdown': -0.082
            },
            {
                'id': 'multi_timeframe',
                'name': 'Multi-Timeframe',
                'status': 'Active',
                'total_trades': 89,
                'winning_trades': 64,
                'total_return': 0.452,
                'sharpe_ratio': 2.12,
                'max_drawdown': -0.065
            },
            {
                'id': 'ml_based',
                'name': 'ML-Based',
                'status': 'Testing',
                'total_trades': 234,
                'winning_trades': 152,
                'total_return': 0.128,
                'sharpe_ratio': 1.43,
                'max_drawdown': -0.125
            }
        ]
        
        for strategy in strategies:
            strategy['win_rate'] = strategy['winning_trades'] / strategy['total_trades']
            strategy['avg_trade_return'] = strategy['total_return'] / strategy['total_trades']
        
        return strategies
    
    def calculate_risk_metrics(self, returns: pd.Series) -> Dict[str, float]:
        """リスクメトリクスを計算"""
        # VaR (95%)
        var_95 = np.percentile(returns, 5)
        
        # Expected Shortfall
        es = returns[returns <= var_95].mean()
        
        # Sortino Ratio
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std() if len(downside_returns) > 0 else 0
        sortino_ratio = returns.mean() / downside_std if downside_std > 0 else 0
        
        # Calmar Ratio
        max_dd = self._calculate_max_drawdown(returns)
        calmar_ratio = returns.mean() / abs(max_dd) if max_dd != 0 else 0
        
        return {
            'var_95': var_95,
            'expected_shortfall': es,
            'sortino_ratio': sortino_ratio,
            'calmar_ratio': calmar_ratio,
            'max_drawdown': max_dd
        }
    
    def _calculate_max_drawdown(self, returns: pd.Series) -> float:
        """最大ドローダウンを計算"""
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        return drawdown.min()


# チャート生成用のヘルパー関数
def create_portfolio_chart(df: pd.DataFrame) -> Dict[str, Any]:
    """ポートフォリオチャートのデータを生成"""
    chart_data = {
        'dates': df['date'].dt.strftime('%Y-%m-%d').tolist(),
        'values': df['value'].tolist(),
        'returns': (df['daily_return'] * 100).tolist()
    }
    return chart_data


def create_heatmap_data(strategy_results: List[Dict], months: int = 6) -> Dict[str, Any]:
    """月次リターンヒートマップのデータを生成"""
    # 各戦略の月次リターンを生成（デモ）
    strategies = [result['name'] for result in strategy_results]
    month_names = pd.date_range(end=datetime.now(), periods=months, freq='M').strftime('%b %Y')
    
    data = []
    for strategy in strategies:
        monthly_returns = np.random.normal(0.03, 0.05, months) * 100
        data.append(monthly_returns.tolist())
    
    return {
        'strategies': strategies,
        'months': month_names.tolist(),
        'values': data
    }


def format_jpy(value: float) -> str:
    """日本円フォーマット"""
    return f"¥{value:,.0f}"


def format_percentage(value: float, decimal_places: int = 2) -> str:
    """パーセンテージフォーマット"""
    return f"{value:.{decimal_places}f}%"


def get_position_color(side: str) -> str:
    """ポジションの色を取得"""
    return "#00d4aa" if side == "LONG" else "#ff4757"


def calculate_position_pnl(entry_price: float, current_price: float, 
                          size: float, side: str) -> Dict[str, float]:
    """ポジションの損益を計算"""
    if side == "LONG":
        pnl = (current_price - entry_price) * size
        pnl_pct = ((current_price - entry_price) / entry_price) * 100
    else:  # SHORT
        pnl = (entry_price - current_price) * size
        pnl_pct = ((entry_price - current_price) / entry_price) * 100
    
    return {
        'pnl': pnl,
        'pnl_pct': pnl_pct
    }
