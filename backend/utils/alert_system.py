"""
アラートシステム

重要なイベントをリアルタイムで監視・通知するモジュール
"""

import json
import asyncio
import smtplib
import requests
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import queue
import time

from ..config_manager import get_config_manager
from ..logger import get_logger


class AlertLevel(Enum):
    """アラートレベル"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(Enum):
    """アラートタイプ"""
    TRADE_EXECUTED = "trade_executed"
    ORDER_FILLED = "order_filled"
    STOP_LOSS_HIT = "stop_loss_hit"
    TAKE_PROFIT_HIT = "take_profit_hit"
    STRATEGY_ERROR = "strategy_error"
    SYSTEM_ERROR = "system_error"
    API_ERROR = "api_error"
    CONNECTION_LOST = "connection_lost"
    HIGH_DRAWDOWN = "high_drawdown"
    DAILY_LIMIT_REACHED = "daily_limit_reached"
    POSITION_SIZE_WARNING = "position_size_warning"
    MARGIN_CALL = "margin_call"
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"


@dataclass
class Alert:
    """アラートデータクラス"""
    alert_type: AlertType
    level: AlertLevel
    title: str
    message: str
    data: Dict[str, Any]
    timestamp: datetime
    strategy_id: Optional[str] = None
    acknowledged: bool = False
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


class AlertSystem:
    """アラートシステムクラス"""
    
    def __init__(self):
        """初期化"""
        self.config = get_config_manager()
        self.logger = get_logger()
        
        # 設定読み込み
        self.notifications_config = self.config.get('notifications', {})
        
        # アラートキュー
        self.alert_queue = queue.Queue()
        self.recent_alerts: List[Alert] = []
        self.max_recent_alerts = 1000
        
        # 通知設定
        self.slack_enabled = self.notifications_config.get('slack', {}).get('enabled', False)
        self.email_enabled = self.notifications_config.get('email', {}).get('enabled', False)
        
        # 通知トリガー
        self.enabled_triggers = set(self.notifications_config.get('triggers', []))
        
        # コールバック関数
        self.callbacks: List[Callable[[Alert], None]] = []
        
        # 処理スレッド
        self.processing_thread = None
        self.running = False
        
        # 重複防止
        self.alert_cooldown = {}  # {alert_key: last_sent_time}
        self.cooldown_seconds = 300  # 5分間の重複防止
        
        self.logger.info("アラートシステムを初期化しました")
    
    def start(self):
        """アラートシステムを開始"""
        if self.running:
            return
        
        self.running = True
        self.processing_thread = threading.Thread(target=self._process_alerts, daemon=True)
        self.processing_thread.start()
        
        self.logger.info("アラートシステムを開始しました")
        
        # システム開始アラート
        self.send_alert(
            AlertType.SYSTEM_STARTUP,
            AlertLevel.INFO,
            "システム開始",
            "GMOコイン自動売買システムが開始されました",
            {}
        )
    
    def stop(self):
        """アラートシステムを停止"""
        if not self.running:
            return
        
        # システム停止アラート
        self.send_alert(
            AlertType.SYSTEM_SHUTDOWN,
            AlertLevel.INFO,
            "システム停止",
            "GMOコイン自動売買システムが停止されました",
            {}
        )
        
        self.running = False
        
        # 処理スレッドの終了を待つ
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=5)
        
        self.logger.info("アラートシステムを停止しました")
    
    def send_alert(self, 
                   alert_type: AlertType, 
                   level: AlertLevel, 
                   title: str, 
                   message: str, 
                   data: Dict[str, Any],
                   strategy_id: Optional[str] = None):
        """
        アラートを送信
        
        Args:
            alert_type: アラートタイプ
            level: アラートレベル
            title: タイトル
            message: メッセージ
            data: 詳細データ
            strategy_id: 戦略ID（オプション）
        """
        # トリガーチェック
        if alert_type.value not in self.enabled_triggers:
            return
        
        # 重複チェック
        alert_key = f"{alert_type.value}:{title}"
        now = time.time()
        
        if alert_key in self.alert_cooldown:
            last_sent = self.alert_cooldown[alert_key]
            if now - last_sent < self.cooldown_seconds:
                return  # 重複防止でスキップ
        
        self.alert_cooldown[alert_key] = now
        
        # アラートオブジェクト作成
        alert = Alert(
            alert_type=alert_type,
            level=level,
            title=title,
            message=message,
            data=data,
            timestamp=datetime.now(),
            strategy_id=strategy_id
        )
        
        # キューに追加
        self.alert_queue.put(alert)
        
        # 最近のアラートに追加
        self.recent_alerts.insert(0, alert)
        if len(self.recent_alerts) > self.max_recent_alerts:
            self.recent_alerts.pop()
        
        # ログ出力
        self.logger.warning(f"アラート: [{level.value.upper()}] {title} - {message}")
    
    def _process_alerts(self):
        """アラート処理スレッド"""
        while self.running:
            try:
                # タイムアウト付きでアラートを取得
                alert = self.alert_queue.get(timeout=1)
                
                # 各通知チャネルに送信
                self._send_to_channels(alert)
                
                # コールバック実行
                for callback in self.callbacks:
                    try:
                        callback(alert)
                    except Exception as e:
                        self.logger.error(f"アラートコールバックエラー: {e}")
                
                self.alert_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"アラート処理エラー: {e}")
    
    def _send_to_channels(self, alert: Alert):
        """各通知チャネルにアラートを送信"""
        try:
            # Slack通知
            if self.slack_enabled:
                self._send_to_slack(alert)
            
            # Email通知
            if self.email_enabled:
                self._send_to_email(alert)
                
        except Exception as e:
            self.logger.error(f"通知送信エラー: {e}")
    
    def _send_to_slack(self, alert: Alert):
        """Slackに通知を送信"""
        try:
            slack_config = self.notifications_config.get('slack', {})
            webhook_url = slack_config.get('webhook_url', '')
            
            if not webhook_url:
                return
            
            # チャネル選択
            channels = slack_config.get('channels', {})
            if alert.alert_type in [AlertType.TRADE_EXECUTED, AlertType.ORDER_FILLED]:
                channel = channels.get('trades', '#trading-alerts')
            elif alert.level in [AlertLevel.ERROR, AlertLevel.CRITICAL]:
                channel = channels.get('errors', '#trading-errors')
            else:
                channel = channels.get('daily_report', '#trading-reports')
            
            # メッセージ作成
            color = {
                AlertLevel.INFO: "good",
                AlertLevel.WARNING: "warning", 
                AlertLevel.ERROR: "danger",
                AlertLevel.CRITICAL: "danger"
            }.get(alert.level, "good")
            
            payload = {
                "channel": channel,
                "username": "TradingBot",
                "icon_emoji": ":robot_face:",
                "attachments": [{
                    "color": color,
                    "title": alert.title,
                    "text": alert.message,
                    "fields": [
                        {
                            "title": "時刻",
                            "value": alert.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                            "short": True
                        },
                        {
                            "title": "レベル",
                            "value": alert.level.value.upper(),
                            "short": True
                        }
                    ],
                    "footer": "GMOコイン自動売買システム",
                    "ts": int(alert.timestamp.timestamp())
                }]
            }
            
            # 戦略情報を追加
            if alert.strategy_id:
                payload["attachments"][0]["fields"].append({
                    "title": "戦略",
                    "value": alert.strategy_id,
                    "short": True
                })
            
            # 詳細データを追加
            if alert.data:
                detail_text = "\n".join([f"• {k}: {v}" for k, v in alert.data.items()])
                payload["attachments"][0]["fields"].append({
                    "title": "詳細",
                    "value": detail_text,
                    "short": False
                })
            
            # Slack API呼び出し
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
        except Exception as e:
            self.logger.error(f"Slack通知エラー: {e}")
    
    def _send_to_email(self, alert: Alert):
        """Email通知を送信"""
        try:
            email_config = self.notifications_config.get('email', {})
            
            smtp_server = email_config.get('smtp_server', 'smtp.gmail.com')
            smtp_port = email_config.get('smtp_port', 587)
            from_address = email_config.get('from_address', '')
            to_addresses = email_config.get('to_addresses', [])
            # セキュリティ強化: 環境変数からパスワードを取得
            password = os.getenv('GMAIL_APP_PASSWORD', '')
            
            if not all([from_address, to_addresses, password]):
                return
            
            # メッセージ作成
            msg = MIMEMultipart()
            msg['From'] = from_address
            msg['To'] = ', '.join(to_addresses)
            msg['Subject'] = f"[{alert.level.value.upper()}] {alert.title}"
            
            # 本文作成
            body = f"""
GMOコイン自動売買システムからのアラートです。

タイトル: {alert.title}
レベル: {alert.level.value.upper()}
時刻: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
戦略: {alert.strategy_id or 'システム'}

メッセージ:
{alert.message}

詳細データ:
{json.dumps(alert.data, indent=2, ensure_ascii=False)}

---
GMOコイン自動売買システム
"""
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # SMTP送信
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(from_address, password)
                server.send_message(msg)
            
        except Exception as e:
            self.logger.error(f"Email通知エラー: {e}")
    
    def add_callback(self, callback: Callable[[Alert], None]):
        """コールバック関数を追加"""
        self.callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[Alert], None]):
        """コールバック関数を削除"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
    
    def get_recent_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """最近のアラートを取得（フロントエンド用）"""
        alerts = self.recent_alerts[:limit]
        
        formatted_alerts = []
        for alert in alerts:
            formatted_alerts.append({
                'id': alert.id,  # UUID使用でプロセス間一意性を保証
                'type': alert.alert_type.value,
                'level': alert.level.value,
                'title': alert.title,
                'message': alert.message,
                'timestamp': alert.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'strategy': alert.strategy_id or 'システム',
                'acknowledged': alert.acknowledged,
                'data': alert.data
            })
        
        return formatted_alerts
    
    def acknowledge_alert(self, alert_id: str):
        """アラートを確認済みにマーク"""
        for alert in self.recent_alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                break
    
    def clear_alerts(self):
        """アラート履歴をクリア"""
        self.recent_alerts.clear()
        self.logger.info("アラート履歴をクリアしました")
    
    def get_alert_statistics(self, days: int = 7) -> Dict[str, Any]:
        """アラート統計を取得"""
        cutoff_time = datetime.now() - timedelta(days=days)
        recent = [a for a in self.recent_alerts if a.timestamp >= cutoff_time]
        
        stats = {
            'total_alerts': len(recent),
            'by_level': {},
            'by_type': {},
            'by_strategy': {},
            'acknowledged_count': sum(1 for a in recent if a.acknowledged)
        }
        
        # レベル別集計
        for level in AlertLevel:
            stats['by_level'][level.value] = len([a for a in recent if a.level == level])
        
        # タイプ別集計
        for alert_type in AlertType:
            count = len([a for a in recent if a.alert_type == alert_type])
            if count > 0:
                stats['by_type'][alert_type.value] = count
        
        # 戦略別集計
        for alert in recent:
            strategy = alert.strategy_id or 'システム'
            stats['by_strategy'][strategy] = stats['by_strategy'].get(strategy, 0) + 1
        
        return stats
    
    # 便利メソッド
    def alert_trade_executed(self, trade_data: Dict[str, Any], strategy_id: str = None):
        """取引実行アラート"""
        self.send_alert(
            AlertType.TRADE_EXECUTED,
            AlertLevel.INFO,
            "取引実行",
            f"{trade_data.get('side', '')} {trade_data.get('quantity', 0)} {trade_data.get('pair', '')} @ ¥{trade_data.get('price', 0):,.0f}",
            trade_data,
            strategy_id
        )
    
    def alert_error(self, error_type: str, error_message: str, details: Dict[str, Any] = None):
        """エラーアラート"""
        self.send_alert(
            AlertType.SYSTEM_ERROR,
            AlertLevel.ERROR,
            f"システムエラー: {error_type}",
            error_message,
            details or {}
        )
    
    def alert_strategy_error(self, strategy_id: str, error_message: str, details: Dict[str, Any] = None):
        """戦略エラーアラート"""
        self.send_alert(
            AlertType.STRATEGY_ERROR,
            AlertLevel.WARNING,
            f"戦略エラー: {strategy_id}",
            error_message,
            details or {},
            strategy_id
        )
    
    def alert_high_drawdown(self, current_drawdown: float, max_allowed: float):
        """高ドローダウンアラート"""
        self.send_alert(
            AlertType.HIGH_DRAWDOWN,
            AlertLevel.WARNING,
            "高ドローダウン警告",
            f"現在のドローダウン {current_drawdown:.2f}% が上限 {max_allowed:.2f}% を超えています",
            {
                'current_drawdown': current_drawdown,
                'max_allowed': max_allowed
            }
        )


# シングルトンインスタンス
_alert_system: Optional[AlertSystem] = None


def get_alert_system() -> AlertSystem:
    """AlertSystemのシングルトンインスタンスを取得"""
    global _alert_system
    if _alert_system is None:
        _alert_system = AlertSystem()
    return _alert_system 