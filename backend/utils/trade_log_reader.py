"""
取引ログリーダー

取引ログファイルからデータを読み込み、分析・表示用に整形するモジュール
"""

import os
import json
import csv
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from ..config_manager import get_config_manager
from ..logger import get_logger


@dataclass
class TradeLogEntry:
    """取引ログエントリー"""
    timestamp: datetime
    pair: str
    side: str
    quantity: float
    price: float
    fee: float
    realized_pnl: float
    order_id: str
    execution_id: str
    strategy: Optional[str] = None
    notes: Optional[str] = None


class TradeLogReader:
    """取引ログリーダークラス"""
    
    def __init__(self):
        """初期化"""
        self.config = get_config_manager()
        self.logger = get_logger()
        
        # ログディレクトリパス
        trade_log_config = self.config.get('logging.trade_log', {})
        self.log_path = Path(trade_log_config.get('path', './logs/trades'))
        self.format_type = trade_log_config.get('format', 'csv')
        
        # フィールド定義
        self.fields = trade_log_config.get('fields', [
            'timestamp', 'pair', 'side', 'quantity', 'price', 
            'fee', 'realized_pnl', 'order_id', 'execution_id'
        ])
    
    def get_trade_logs(self, days: int = 30) -> List[TradeLogEntry]:
        """
        過去N日分の取引ログを取得
        
        Args:
            days: 取得日数
            
        Returns:
            取引ログエントリーのリスト
        """
        try:
            all_trades = []
            start_date = datetime.now() - timedelta(days=days)
            
            # ログディレクトリが存在しない場合は作成
            self.log_path.mkdir(parents=True, exist_ok=True)
            
            # 対象期間のファイルを取得
            for date_offset in range(days + 1):
                target_date = start_date + timedelta(days=date_offset)
                date_str = target_date.strftime('%Y%m%d')
                
                if self.format_type == 'csv':
                    file_path = self.log_path / f"trades_{date_str}.csv"
                    trades = self._read_csv_log(file_path)
                elif self.format_type == 'json':
                    file_path = self.log_path / f"trades_{date_str}.jsonl"
                    trades = self._read_json_log(file_path)
                else:
                    continue
                
                all_trades.extend(trades)
            
            # タイムスタンプでソート（新しい順）
            all_trades.sort(key=lambda x: x.timestamp, reverse=True)
            
            self.logger.info(f"取引ログ取得完了: {len(all_trades)}件 (過去{days}日)")
            return all_trades
            
        except Exception as e:
            self.logger.error(f"取引ログ取得エラー: {e}")
            return []
    
    def _read_csv_log(self, file_path: Path) -> List[TradeLogEntry]:
        """CSV形式のログファイルを読み込み"""
        if not file_path.exists():
            return []
        
        trades = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    trade = self._parse_trade_entry(row)
                    if trade:
                        trades.append(trade)
        except Exception as e:
            self.logger.error(f"CSVログ読み込みエラー {file_path}: {e}")
        
        return trades
    
    def _read_json_log(self, file_path: Path) -> List[TradeLogEntry]:
        """JSON形式のログファイルを読み込み"""
        if not file_path.exists():
            return []
        
        trades = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line.strip())
                        trade = self._parse_trade_entry(data)
                        if trade:
                            trades.append(trade)
        except Exception as e:
            self.logger.error(f"JSONログ読み込みエラー {file_path}: {e}")
        
        return trades
    
    def _parse_trade_entry(self, data: Dict[str, Any]) -> Optional[TradeLogEntry]:
        """ログデータをTradeLogEntryに変換"""
        try:
            # タイムスタンプ解析
            timestamp_str = data.get('timestamp', '')
            if timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                return None
            
            return TradeLogEntry(
                timestamp=timestamp,
                pair=data.get('pair', ''),
                side=data.get('side', ''),
                quantity=float(data.get('quantity', 0)),
                price=float(data.get('price', 0)),
                fee=float(data.get('fee', 0)),
                realized_pnl=float(data.get('realized_pnl', 0)),
                order_id=data.get('order_id', ''),
                execution_id=data.get('execution_id', ''),
                strategy=data.get('strategy'),
                notes=data.get('notes')
            )
        except (ValueError, TypeError) as e:
            self.logger.warning(f"取引ログエントリー解析エラー: {e}, data: {data}")
            return None
    
    def get_daily_summary(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        日次サマリーを生成
        
        Args:
            days: 集計日数
            
        Returns:
            日次サマリーのリスト
        """
        trades = self.get_trade_logs(days)
        
        # 日付ごとにグループ化
        daily_data = {}
        for trade in trades:
            date_key = trade.timestamp.date().isoformat()
            
            if date_key not in daily_data:
                daily_data[date_key] = {
                    'date': date_key,
                    'total_trades': 0,
                    'total_volume': 0,
                    'total_pnl': 0,
                    'total_fees': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'buy_trades': 0,
                    'sell_trades': 0
                }
            
            data = daily_data[date_key]
            data['total_trades'] += 1
            data['total_volume'] += trade.quantity * trade.price
            data['total_pnl'] += trade.realized_pnl
            data['total_fees'] += trade.fee
            
            if trade.realized_pnl > 0:
                data['winning_trades'] += 1
            elif trade.realized_pnl < 0:
                data['losing_trades'] += 1
            
            if trade.side.upper() == 'BUY':
                data['buy_trades'] += 1
            else:
                data['sell_trades'] += 1
        
        # 勝率を計算
        for data in daily_data.values():
            total = data['winning_trades'] + data['losing_trades']
            data['win_rate'] = (data['winning_trades'] / total * 100) if total > 0 else 0
        
        # 日付順にソート
        summary_list = list(daily_data.values())
        summary_list.sort(key=lambda x: x['date'], reverse=True)
        
        return summary_list
    
    def get_strategy_performance(self, days: int = 30) -> Dict[str, Dict[str, Any]]:
        """
        戦略別パフォーマンスを分析
        
        Args:
            days: 分析日数
            
        Returns:
            戦略別パフォーマンス辞書
        """
        trades = self.get_trade_logs(days)
        
        strategy_data = {}
        for trade in trades:
            strategy = trade.strategy or 'unknown'
            
            if strategy not in strategy_data:
                strategy_data[strategy] = {
                    'strategy': strategy,
                    'total_trades': 0,
                    'total_pnl': 0,
                    'total_fees': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'total_volume': 0,
                    'trades_detail': []
                }
            
            data = strategy_data[strategy]
            data['total_trades'] += 1
            data['total_pnl'] += trade.realized_pnl
            data['total_fees'] += trade.fee
            data['total_volume'] += trade.quantity * trade.price
            
            if trade.realized_pnl > 0:
                data['winning_trades'] += 1
            elif trade.realized_pnl < 0:
                data['losing_trades'] += 1
            
            data['trades_detail'].append({
                'timestamp': trade.timestamp.isoformat(),
                'pair': trade.pair,
                'side': trade.side,
                'pnl': trade.realized_pnl,
                'fee': trade.fee
            })
        
        # 統計計算
        for data in strategy_data.values():
            total = data['winning_trades'] + data['losing_trades']
            data['win_rate'] = (data['winning_trades'] / total * 100) if total > 0 else 0
            data['avg_pnl'] = data['total_pnl'] / data['total_trades'] if data['total_trades'] > 0 else 0
            data['profit_factor'] = abs(data['total_pnl'] / data['total_fees']) if data['total_fees'] > 0 else 0
        
        return strategy_data
    
    def export_to_dataframe(self, days: int = 30) -> pd.DataFrame:
        """
        取引ログをDataFrameで出力
        
        Args:
            days: 出力日数
            
        Returns:
            取引ログDataFrame
        """
        trades = self.get_trade_logs(days)
        
        if not trades:
            return pd.DataFrame()
        
        data = []
        for trade in trades:
            data.append({
                'timestamp': trade.timestamp,
                'date': trade.timestamp.date(),
                'time': trade.timestamp.time(),
                'pair': trade.pair,
                'side': trade.side,
                'quantity': trade.quantity,
                'price': trade.price,
                'value': trade.quantity * trade.price,
                'fee': trade.fee,
                'realized_pnl': trade.realized_pnl,
                'net_pnl': trade.realized_pnl - trade.fee,
                'order_id': trade.order_id,
                'execution_id': trade.execution_id,
                'strategy': trade.strategy or 'unknown'
            })
        
        df = pd.DataFrame(data)
        return df
    
    def get_recent_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        最近の取引を取得（フロントエンド表示用）
        
        Args:
            limit: 取得件数
            
        Returns:
            取引データのリスト
        """
        trades = self.get_trade_logs(days=7)  # 過去1週間
        
        # 最新の取引から指定件数を取得
        recent_trades = trades[:limit]
        
        # フロントエンド用にフォーマット
        formatted_trades = []
        for trade in recent_trades:
            formatted_trades.append({
                'timestamp': trade.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'pair': trade.pair,
                'side': trade.side,
                'quantity': f"{trade.quantity:.6f}",
                'price': f"¥{trade.price:,.0f}",
                'value': f"¥{trade.quantity * trade.price:,.0f}",
                'fee': f"¥{trade.fee:,.0f}",
                'pnl': f"¥{trade.realized_pnl:,.0f}",
                'net_pnl': f"¥{trade.realized_pnl - trade.fee:,.0f}",
                'strategy': trade.strategy or '手動',
                'order_id': trade.order_id,
                'status': '約定済み'
            })
        
        return formatted_trades


# シングルトンインスタンス
_trade_log_reader: Optional[TradeLogReader] = None


def get_trade_log_reader() -> TradeLogReader:
    """TradeLogReaderのシングルトンインスタンスを取得"""
    global _trade_log_reader
    if _trade_log_reader is None:
        _trade_log_reader = TradeLogReader()
    return _trade_log_reader 