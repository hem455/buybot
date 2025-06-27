"""
ロギングモジュール

システム全体のログ出力を管理するモジュール。
Loguruを使用して、ファイル出力、ローテーション、フォーマット設定を提供。
"""

import sys
import json
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from loguru import logger

from ..config_manager import get_config_manager


class LoggerManager:
    """ロガー管理クラス"""
    
    def __init__(self):
        """初期化"""
        self.config = get_config_manager()
        self.logger = logger
        self.trade_log_path: Optional[Path] = None
        self._setup_logger()
    
    def _setup_logger(self) -> None:
        """ロガーの設定"""
        # 既存のハンドラーをクリア
        self.logger.remove()
        
        # 設定を取得
        log_config = self.config.get_logging_config()
        log_level = log_config.get('level', 'INFO')
        log_format = log_config.get('format', 
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}")
        
        # コンソール出力の設定
        if log_config.get('console', {}).get('enabled', True):
            self.logger.add(
                sys.stdout,
                level=log_level,
                format=log_format,
                colorize=log_config.get('console', {}).get('colorize', True)
            )
        
        # ファイル出力の設定
        if log_config.get('file', {}).get('enabled', True):
            log_path = Path(log_config.get('file', {}).get('path', './logs'))
            log_path.mkdir(parents=True, exist_ok=True)
            
            self.logger.add(
                log_path / "system_{time:YYYY-MM-DD}.log",
                level=log_level,
                format=log_format,
                rotation=log_config.get('file', {}).get('rotation', '10 MB'),
                retention=log_config.get('file', {}).get('retention', '30 days'),
                compression=log_config.get('file', {}).get('compression', 'zip'),
                encoding='utf-8'
            )
        
        # 取引ログの設定
        if log_config.get('trade_log', {}).get('enabled', True):
            trade_log_path = Path(log_config.get('trade_log', {}).get('path', './logs/trades'))
            trade_log_path.mkdir(parents=True, exist_ok=True)
            self.trade_log_path = trade_log_path
    
    def log_trade(self, trade_data: Dict[str, Any]) -> None:
        """
        取引ログを記録する（法的・税務用）
        
        Args:
            trade_data: 取引データ
        """
        if not self.trade_log_path:
            return
        
        # 設定を取得
        trade_log_config = self.config.get('logging.trade_log', {})
        format_type = trade_log_config.get('format', 'csv')
        fields = trade_log_config.get('fields', [
            'timestamp', 'pair', 'side', 'quantity', 'price', 
            'fee', 'realized_pnl', 'order_id', 'execution_id'
        ])
        
        # タイムスタンプを追加
        if 'timestamp' not in trade_data:
            trade_data['timestamp'] = datetime.now().isoformat()
        
        # ファイル名を生成
        date_str = datetime.now().strftime('%Y%m%d')
        
        if format_type == 'csv':
            self._log_trade_csv(trade_data, fields, date_str)
        elif format_type == 'json':
            self._log_trade_json(trade_data, date_str)
        elif format_type == 'parquet':
            self._log_trade_parquet(trade_data, fields, date_str)
        else:
            self.logger.warning(f"不明な取引ログフォーマット: {format_type}")
    
    def _log_trade_csv(self, trade_data: Dict[str, Any], fields: List[str], date_str: str) -> None:
        """CSV形式で取引ログを記録"""
        file_path = self.trade_log_path / f"trades_{date_str}.csv"
        
        # ファイルが存在しない場合はヘッダーを書く
        write_header = not file_path.exists()
        
        with open(file_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
            
            if write_header:
                writer.writeheader()
            
            # 指定されたフィールドのみを書き込む
            row_data = {field: trade_data.get(field, '') for field in fields}
            writer.writerow(row_data)
    
    def _log_trade_json(self, trade_data: Dict[str, Any], date_str: str) -> None:
        """JSON形式で取引ログを記録"""
        file_path = self.trade_log_path / f"trades_{date_str}.jsonl"
        
        with open(file_path, 'a', encoding='utf-8') as f:
            json.dump(trade_data, f, ensure_ascii=False)
            f.write('\n')
    
    def _log_trade_parquet(self, trade_data: Dict[str, Any], fields: List[str], date_str: str) -> None:
        """Parquet形式で取引ログを記録"""
        # Parquetの実装は後で追加（pandasが必要）
        self.logger.warning("Parquet形式の取引ログはまだ実装されていません")
        # 代替としてCSVで記録
        self._log_trade_csv(trade_data, fields, date_str)
    
    def log_signal(self, signal_type: str, strategy: str, details: Dict[str, Any]) -> None:
        """
        シグナルログを記録する
        
        Args:
            signal_type: シグナルタイプ（BUY, SELL, HOLD等）
            strategy: 戦略名
            details: 詳細情報
        """
        # Signalオブジェクトなどを文字列に変換
        def convert_to_serializable(obj):
            if hasattr(obj, 'value'):
                return obj.value
            elif hasattr(obj, '__dict__'):
                return str(obj)
            return obj
        
        # 詳細情報をシリアライズ可能に変換
        serializable_details = {}
        for key, value in details.items():
            serializable_details[key] = convert_to_serializable(value)
        
        self.logger.info(
            f"シグナル発生 | タイプ: {signal_type} | 戦略: {strategy} | 詳細: {json.dumps(serializable_details, ensure_ascii=False)}"
        )
    
    def log_order(self, action: str, order_data: Dict[str, Any]) -> None:
        """
        注文ログを記録する
        
        Args:
            action: アクション（PLACED, FILLED, CANCELLED等）
            order_data: 注文データ
        """
        self.logger.info(
            f"注文 | アクション: {action} | データ: {json.dumps(order_data, ensure_ascii=False)}"
        )
    
    def log_position(self, position_data: Dict[str, Any]) -> None:
        """
        ポジションログを記録する
        
        Args:
            position_data: ポジションデータ
        """
        self.logger.info(
            f"ポジション更新 | データ: {json.dumps(position_data, ensure_ascii=False)}"
        )
    
    def log_error(self, error_type: str, error_message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        エラーログを記録する
        
        Args:
            error_type: エラータイプ
            error_message: エラーメッセージ
            details: 詳細情報
        """
        error_data = {
            'type': error_type,
            'message': error_message,
            'details': details or {}
        }
        self.logger.error(
            f"エラー発生 | {json.dumps(error_data, ensure_ascii=False)}"
        )
    
    def log_api_call(self, endpoint: str, method: str, status_code: int, response_time: float) -> None:
        """
        APIコールログを記録する
        
        Args:
            endpoint: エンドポイント
            method: HTTPメソッド
            status_code: ステータスコード
            response_time: レスポンス時間（秒）
        """
        self.logger.debug(
            f"API呼び出し | {method} {endpoint} | ステータス: {status_code} | 応答時間: {response_time:.3f}秒"
        )
    
    def log_performance(self, metrics: Dict[str, Any]) -> None:
        """
        パフォーマンスメトリクスを記録する
        
        Args:
            metrics: メトリクスデータ
        """
        self.logger.info(
            f"パフォーマンス | {json.dumps(metrics, ensure_ascii=False)}"
        )


# シングルトンインスタンス
_logger_manager: Optional[LoggerManager] = None


def get_logger_manager() -> LoggerManager:
    """LoggerManagerのシングルトンインスタンスを取得する"""
    global _logger_manager
    if _logger_manager is None:
        _logger_manager = LoggerManager()
    return _logger_manager


def get_logger():
    """ロガーインスタンスを取得する"""
    return get_logger_manager().logger


# 便利な関数
def log_trade(trade_data: Dict[str, Any]) -> None:
    """取引ログを記録する"""
    get_logger_manager().log_trade(trade_data)


def log_signal(signal_type: str, strategy: str, details: Dict[str, Any]) -> None:
    """シグナルログを記録する"""
    get_logger_manager().log_signal(signal_type, strategy, details)


def log_order(action: str, order_data: Dict[str, Any]) -> None:
    """注文ログを記録する"""
    get_logger_manager().log_order(action, order_data)


def log_error(error_type: str, error_message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """エラーログを記録する"""
    get_logger_manager().log_error(error_type, error_message, details)
