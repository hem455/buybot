"""
総資産履歴データベース管理

毎日の総資産推移を永続化し、長期的なパフォーマンス分析を可能にします。
"""

import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
import threading

from ..logger import get_logger


class AssetHistoryDB:
    """総資産履歴データベース管理クラス"""
    
    def __init__(self, db_path: str = "data/asset_history.db"):
        """
        初期化
        
        Args:
            db_path: データベースファイルパス
        """
        self.db_path = db_path
        self.logger = get_logger()
        
        # データディレクトリを確保
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # データベースを初期化
        self._init_database()
    
    def _init_database(self):
        """データベースとテーブルを初期化"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 総資産履歴テーブル
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS asset_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT UNIQUE NOT NULL,
                        timestamp TEXT NOT NULL,
                        total_assets REAL NOT NULL,
                        jpy_balance REAL NOT NULL,
                        spot_value REAL NOT NULL,
                        margin_pnl REAL NOT NULL,
                        asset_breakdown TEXT,
                        notes TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 日次サマリーテーブル
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS daily_summary (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT UNIQUE NOT NULL,
                        total_trades INTEGER DEFAULT 0,
                        realized_pnl REAL DEFAULT 0,
                        unrealized_pnl REAL DEFAULT 0,
                        commission_paid REAL DEFAULT 0,
                        win_rate REAL DEFAULT 0,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # インデックス作成
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_asset_history_date ON asset_history (date)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_summary_date ON daily_summary (date)")
                
                conn.commit()
                self.logger.info(f"資産履歴データベース初期化完了: {self.db_path}")
                
        except Exception as e:
            self.logger.error(f"データベース初期化エラー: {e}")
            raise
    
    def save_daily_assets(self, 
                         total_assets: float,
                         jpy_balance: float,
                         spot_value: float,
                         margin_pnl: float,
                         asset_breakdown: Dict[str, Any] = None,
                         notes: str = None) -> bool:
        """
        日次総資産データを保存
        
        Args:
            total_assets: 総資産額
            jpy_balance: JPY残高
            spot_value: 現物評価額
            margin_pnl: 証拠金取引損益
            asset_breakdown: 資産内訳詳細
            notes: 備考
            
        Returns:
            保存成功フラグ
        """
        try:
            # UTC基準のタイムゾーン対応日付（データ一貫性確保）
            today = datetime.now(timezone.utc).date().isoformat()
            timestamp = datetime.now(timezone.utc).isoformat()
            
            # 資産内訳をJSON文字列に変換
            breakdown_json = json.dumps(asset_breakdown, ensure_ascii=False) if asset_breakdown else None
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 今日のデータがある場合は更新、ない場合は挿入
                cursor.execute("""
                    INSERT OR REPLACE INTO asset_history 
                    (date, timestamp, total_assets, jpy_balance, spot_value, margin_pnl, asset_breakdown, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (today, timestamp, total_assets, jpy_balance, spot_value, margin_pnl, breakdown_json, notes))
                
                conn.commit()
                self.logger.info(f"日次資産データ保存完了: {today} - 総資産: ¥{total_assets:,.0f}")
                return True
                
        except Exception as e:
            self.logger.error(f"日次資産データ保存エラー: {e}")
            return False
    
    def get_asset_history(self, days: int = 30) -> pd.DataFrame:
        """
        資産履歴を取得
        
        Args:
            days: 取得日数
            
        Returns:
            資産履歴DataFrame
        """
        try:
            # UTC基準の日付計算（タイムゾーン一貫性）
            start_date = (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                query = """
                    SELECT date, timestamp, total_assets, jpy_balance, spot_value, margin_pnl, asset_breakdown
                    FROM asset_history 
                    WHERE date >= ?
                    ORDER BY date ASC
                """
                
                df = pd.read_sql_query(query, conn, params=(start_date,))
                
                if not df.empty:
                    # 日付をdatetimeに変換
                    df['date'] = pd.to_datetime(df['date'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    
                    # 資産内訳を辞書に変換
                    df['asset_breakdown'] = df['asset_breakdown'].apply(
                        lambda x: json.loads(x) if x else {}
                    )
                
                self.logger.info(f"資産履歴取得完了: {len(df)}件 (過去{days}日)")
                return df
                
        except Exception as e:
            self.logger.error(f"資産履歴取得エラー: {e}")
            return pd.DataFrame()
    
    def get_latest_assets(self) -> Optional[Dict[str, Any]]:
        """
        最新の資産データを取得
        
        Returns:
            最新資産データ辞書
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT date, timestamp, total_assets, jpy_balance, spot_value, margin_pnl, asset_breakdown
                    FROM asset_history 
                    ORDER BY date DESC 
                    LIMIT 1
                """)
                
                row = cursor.fetchone()
                if row:
                    return {
                        'date': row[0],
                        'timestamp': row[1],
                        'total_assets': row[2],
                        'jpy_balance': row[3],
                        'spot_value': row[4],
                        'margin_pnl': row[5],
                        'asset_breakdown': json.loads(row[6]) if row[6] else {}
                    }
                
                return None
                
        except Exception as e:
            self.logger.error(f"最新資産データ取得エラー: {e}")
            return None
    
    def save_daily_summary(self,
                          total_trades: int,
                          realized_pnl: float,
                          unrealized_pnl: float,
                          commission_paid: float,
                          win_rate: float) -> bool:
        """
        日次サマリーを保存
        
        Args:
            total_trades: 総取引数
            realized_pnl: 確定損益
            unrealized_pnl: 未実現損益
            commission_paid: 手数料支払額
            win_rate: 勝率
            
        Returns:
            保存成功フラグ
        """
        try:
            # UTC基準のタイムゾーン対応日付（データ一貫性確保）
            today = datetime.now(timezone.utc).date().isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO daily_summary 
                    (date, total_trades, realized_pnl, unrealized_pnl, commission_paid, win_rate)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (today, total_trades, realized_pnl, unrealized_pnl, commission_paid, win_rate))
                
                conn.commit()
                self.logger.info(f"日次サマリー保存完了: {today}")
                return True
                
        except Exception as e:
            self.logger.error(f"日次サマリー保存エラー: {e}")
            return False
    
    def get_performance_stats(self, days: int = 30) -> Dict[str, Any]:
        """
        パフォーマンス統計を取得
        
        Args:
            days: 集計日数
            
        Returns:
            統計辞書
        """
        try:
            # UTC基準の日付計算（タイムゾーン一貫性）
            start_date = (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                # 資産推移統計
                asset_query = """
                    SELECT 
                        MIN(total_assets) as min_assets,
                        MAX(total_assets) as max_assets,
                        AVG(total_assets) as avg_assets,
                        COUNT(*) as total_days
                    FROM asset_history 
                    WHERE date >= ?
                """
                
                asset_stats = pd.read_sql_query(asset_query, conn, params=(start_date,)).iloc[0]
                
                # サマリー統計
                summary_query = """
                    SELECT 
                        SUM(total_trades) as total_trades,
                        SUM(realized_pnl) as total_realized_pnl,
                        AVG(win_rate) as avg_win_rate,
                        SUM(commission_paid) as total_commission
                    FROM daily_summary 
                    WHERE date >= ?
                """
                
                summary_stats = pd.read_sql_query(summary_query, conn, params=(start_date,)).iloc[0]
                
                # 最高・最低資産額の日付を取得
                peak_query = """
                    SELECT date, total_assets FROM asset_history 
                    WHERE date >= ? AND total_assets = (
                        SELECT MAX(total_assets) FROM asset_history WHERE date >= ?
                    )
                    LIMIT 1
                """
                
                peak_data = pd.read_sql_query(peak_query, conn, params=(start_date, start_date))
                
                # 統計をまとめて返却
                return {
                    'period_days': int(asset_stats['total_days'] or 0),
                    'min_assets': float(asset_stats['min_assets'] or 0),
                    'max_assets': float(asset_stats['max_assets'] or 0),
                    'avg_assets': float(asset_stats['avg_assets'] or 0),
                    'peak_date': peak_data.iloc[0]['date'] if not peak_data.empty else None,
                    'peak_assets': float(peak_data.iloc[0]['total_assets']) if not peak_data.empty else 0,
                    'total_trades': int(summary_stats['total_trades'] or 0),
                    'total_realized_pnl': float(summary_stats['total_realized_pnl'] or 0),
                    'avg_win_rate': float(summary_stats['avg_win_rate'] or 0),
                    'total_commission': float(summary_stats['total_commission'] or 0)
                }
                
        except Exception as e:
            self.logger.error(f"パフォーマンス統計取得エラー: {e}")
            return {}
    
    def cleanup_old_data(self, keep_days: int = 365) -> bool:
        """
        古いデータを削除（データベースサイズ管理）
        
        Args:
            keep_days: 保持日数
            
        Returns:
            削除成功フラグ
        """
        try:
            # UTC基準の日付計算（タイムゾーン一貫性）
            cutoff_date = (datetime.now(timezone.utc).date() - timedelta(days=keep_days)).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 古いデータを削除
                cursor.execute("DELETE FROM asset_history WHERE date < ?", (cutoff_date,))
                cursor.execute("DELETE FROM daily_summary WHERE date < ?", (cutoff_date,))
                
                deleted_count = cursor.rowcount
                conn.commit()
                
                # データベースサイズを最適化
                cursor.execute("VACUUM")
                
                self.logger.info(f"古いデータ削除完了: {deleted_count}件 (保持期間: {keep_days}日)")
                return True
                
        except Exception as e:
            self.logger.error(f"古いデータ削除エラー: {e}")
            return False


# シングルトンインスタンス（スレッドセーフ）
_asset_history_db: Optional[AssetHistoryDB] = None
_lock = threading.Lock()


def get_asset_history_db() -> AssetHistoryDB:
    """スレッドセーフなAssetHistoryDBシングルトンインスタンスを取得"""
    global _asset_history_db
    
    # ダブルチェックロッキングパターン（パフォーマンス最適化）
    if _asset_history_db is None:
        with _lock:
            # ロック取得後に再度チェック（他のスレッドが初期化済みの可能性）
            if _asset_history_db is None:
                _asset_history_db = AssetHistoryDB()
    
    return _asset_history_db 