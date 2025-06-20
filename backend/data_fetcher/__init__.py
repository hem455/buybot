"""
データ取得モジュール
"""

from .base import BaseDataFetcher, DataValidator, DataStorage, RateLimiter
from .rest_api import GMOCoinRESTFetcher
from .websocket_api import GMOCoinWebSocketFetcher

# Alias for backward compatibility or more generic naming
GMOCoinDataFetcher = GMOCoinRESTFetcher

__all__ = [
    'BaseDataFetcher',
    'DataValidator', 
    'DataStorage',
    'RateLimiter',
    'GMOCoinRESTFetcher',
    'GMOCoinWebSocketFetcher',
    'GMOCoinDataFetcher'
]
