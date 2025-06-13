"""
設定管理モジュール

システム全体の設定を管理するモジュール。
YAMLファイルと環境変数から設定を読み込み、統合的に管理する。
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from dotenv import load_dotenv


class ConfigManager:
    """設定管理クラス"""
    
    def __init__(self, config_path: str = "config/config.yaml", env_path: str = ".env"):
        """
        初期化
        
        Args:
            config_path: 設定ファイルのパス
            env_path: 環境変数ファイルのパス
        """
        self.config_path = Path(config_path)
        self.env_path = Path(env_path)
        self._config: Dict[str, Any] = {}
        self._env_config: Dict[str, Any] = {}
        
        # 設定を読み込む
        self.load_config()
    
    def load_config(self) -> None:
        """設定を読み込む"""
        # 環境変数を読み込む
        if self.env_path.exists():
            load_dotenv(self.env_path)
        
        # 環境変数から機密情報を取得
        self._load_env_variables()
        
        # YAMLファイルから設定を読み込む
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        else:
            raise FileNotFoundError(f"設定ファイルが見つかりません: {self.config_path}")
        
        # 環境変数で上書き
        self._merge_env_config()
        
        # 設定値の検証
        self._validate_config()
    
    def _load_env_variables(self) -> None:
        """環境変数から機密情報を読み込む"""
        # GMOコインAPIキー
        self._env_config['gmo_api_key'] = os.getenv('GMO_API_KEY')
        self._env_config['gmo_api_secret'] = os.getenv('GMO_API_SECRET')
        
        # 環境設定
        self._env_config['env'] = os.getenv('ENV', 'development')
        self._env_config['debug'] = os.getenv('DEBUG', 'False').lower() == 'true'
        
        # データベース設定
        self._env_config['database_url'] = os.getenv('DATABASE_URL')
        
        # ログ設定
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        if log_level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            self._env_config['log_level'] = log_level
        
        # 通知設定
        self._env_config['slack_webhook_url'] = os.getenv('SLACK_WEBHOOK_URL')
        self._env_config['email_smtp_server'] = os.getenv('EMAIL_SMTP_SERVER')
        self._env_config['email_smtp_port'] = os.getenv('EMAIL_SMTP_PORT')
        self._env_config['email_from'] = os.getenv('EMAIL_FROM')
        self._env_config['email_password'] = os.getenv('EMAIL_PASSWORD')
        self._env_config['email_to'] = os.getenv('EMAIL_TO')
    
    def _merge_env_config(self) -> None:
        """環境変数の設定をマージする"""
        # ログレベルの上書き
        if 'log_level' in self._env_config:
            self._config['logging']['level'] = self._env_config['log_level']
        
        # Slack設定の上書き
        if self._env_config.get('slack_webhook_url'):
            self._config['notifications']['slack']['webhook_url'] = self._env_config['slack_webhook_url']
            self._config['notifications']['slack']['enabled'] = True
        
        # Email設定の上書き
        if self._env_config.get('email_from'):
            self._config['notifications']['email']['from_address'] = self._env_config['email_from']
            if self._env_config.get('email_to'):
                self._config['notifications']['email']['to_addresses'] = [self._env_config['email_to']]
            self._config['notifications']['email']['enabled'] = True
    
    def _validate_config(self) -> None:
        """設定値を検証する"""
        # 必須項目の確認
        if not self._env_config.get('gmo_api_key') or not self._env_config.get('gmo_api_secret'):
            if self._env_config.get('env') == 'production':
                raise ValueError("本番環境ではAPIキーが必須です")
        
        # 数値範囲の検証
        risk_per_trade = self.get('risk_management.position_sizing.risk_per_trade', 0.02)
        if not 0 < risk_per_trade <= 0.1:
            raise ValueError(f"リスク率が不正です: {risk_per_trade} (0 < x <= 0.1)")
        
        max_drawdown = self.get('risk_management.max_drawdown_percentage', 0.20)
        if not 0 < max_drawdown <= 1.0:
            raise ValueError(f"最大ドローダウン率が不正です: {max_drawdown} (0 < x <= 1.0)")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        設定値を取得する
        
        Args:
            key: 設定キー（ドット区切りで階層を指定）
            default: デフォルト値
        
        Returns:
            設定値
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """
        設定値を設定する（実行時のみ、ファイルには保存されない）
        
        Args:
            key: 設定キー（ドット区切りで階層を指定）
            value: 設定値
        """
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def get_api_credentials(self) -> Dict[str, str]:
        """APIクレデンシャルを取得する"""
        return {
            'api_key': self._env_config.get('gmo_api_key', ''),
            'api_secret': self._env_config.get('gmo_api_secret', '')
        }
    
    def get_exchange_config(self) -> Dict[str, Any]:
        """取引所設定を取得する"""
        return self.get('exchange', {})
    
    def get_trading_config(self) -> Dict[str, Any]:
        """取引設定を取得する"""
        return self.get('trading', {})
    
    def get_strategy_config(self, strategy_id: Optional[str] = None) -> Dict[str, Any]:
        """
        戦略設定を取得する
        
        Args:
            strategy_id: 戦略ID（指定しない場合はデフォルト戦略）
        
        Returns:
            戦略設定
        """
        if strategy_id is None:
            strategy_id = self.get('strategies.default', 'simple_ma_cross')
        
        strategies = self.get('strategies.available', {})
        if strategy_id not in strategies:
            raise ValueError(f"戦略が見つかりません: {strategy_id}")
        
        return strategies[strategy_id]
    
    def get_risk_config(self) -> Dict[str, Any]:
        """リスク管理設定を取得する"""
        return self.get('risk_management', {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """ロギング設定を取得する"""
        return self.get('logging', {})
    
    def is_debug_mode(self) -> bool:
        """デバッグモードかどうか"""
        return self._env_config.get('debug', False)
    
    def is_production(self) -> bool:
        """本番環境かどうか"""
        return self._env_config.get('env') == 'production'
    
    def reload(self) -> None:
        """設定を再読み込みする"""
        self._config = {}
        self._env_config = {}
        self.load_config()


# シングルトンインスタンス
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """ConfigManagerのシングルトンインスタンスを取得する"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_config(key: str, default: Any = None) -> Any:
    """
    設定値を取得する（ショートカット関数）
    
    Args:
        key: 設定キー
        default: デフォルト値
    
    Returns:
        設定値
    """
    return get_config_manager().get(key, default)
