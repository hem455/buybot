"""
ConfigManagerのテスト
"""

import pytest
from pathlib import Path
import os
import tempfile
import yaml

from backend.config_manager import ConfigManager


class TestConfigManager:
    
    @pytest.fixture
    def temp_config_file(self):
        """一時的な設定ファイルを作成"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config_data = {
                'system': {
                    'name': 'Test System',
                    'version': '1.0.0'
                },
                'trading': {
                    'symbol': 'BTC_JPY',
                    'min_order_size': 0.0001
                },
                'risk_management': {
                    'position_sizing': {
                        'risk_per_trade': 0.02
                    }
                }
            }
            yaml.dump(config_data, f)
            temp_path = f.name
        
        yield temp_path
        
        # クリーンアップ
        os.unlink(temp_path)
    
    def test_load_config(self, temp_config_file):
        """設定の読み込みテスト"""
        config = ConfigManager(config_path=temp_config_file)
        
        assert config.get('system.name') == 'Test System'
        assert config.get('system.version') == '1.0.0'
        assert config.get('trading.symbol') == 'BTC_JPY'
    
    def test_get_with_default(self, temp_config_file):
        """デフォルト値のテスト"""
        config = ConfigManager(config_path=temp_config_file)
        
        # 存在しないキー
        assert config.get('nonexistent.key', 'default') == 'default'
        
        # 存在するキー
        assert config.get('trading.symbol', 'default') == 'BTC_JPY'
    
    def test_set_config(self, temp_config_file):
        """設定の更新テスト"""
        config = ConfigManager(config_path=temp_config_file)
        
        # 新しい値を設定
        config.set('trading.new_parameter', 100)
        assert config.get('trading.new_parameter') == 100
        
        # 既存の値を更新
        config.set('trading.symbol', 'ETH_JPY')
        assert config.get('trading.symbol') == 'ETH_JPY'
    
    def test_validate_config(self, temp_config_file):
        """設定の検証テスト"""
        config = ConfigManager(config_path=temp_config_file)
        
        # 不正なリスク率を設定
        config.set('risk_management.position_sizing.risk_per_trade', 0.5)
        
        with pytest.raises(ValueError):
            config._validate_config()
