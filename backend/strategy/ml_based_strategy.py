"""
機械学習ベース戦略

特徴量エンジニアリングと機械学習モデルを使用して売買シグナルを生成する戦略。
シンプルなランダムフォレストモデルを使用。
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple, Optional, List
import joblib
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

from .base_strategy import BaseStrategy, Signal
from ..logger import get_logger


class MLBasedStrategy(BaseStrategy):
    """
    機械学習ベース戦略
    
    過去のデータから特徴量を生成し、機械学習モデルで売買判断を行う。
    """
    
    def __init__(self, strategy_id: str = 'ml_based', params: Optional[Dict[str, Any]] = None):
        """
        初期化
        
        Args:
            strategy_id: 戦略ID
            params: 戦略パラメータ
        """
        # デフォルトパラメータ
        default_params = {
            'lookback_period': 20,      # 特徴量生成の振り返り期間
            'prediction_threshold': 0.6, # 予測確率の閾値
            'min_data_points': 100,     # 最小データ数
            'retrain_interval': 1000,   # 再学習間隔（バー数）
            'feature_set': 'basic',     # 特徴量セット（basic/advanced）
            'model_type': 'random_forest',  # モデルタイプ
            'use_pretrained': False,    # 事前学習済みモデルを使用
        }
        
        super().__init__(strategy_id, {**default_params, **(params or {})})
        
        # モデル関連
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = []
        self.last_train_index = 0
        self.model_path = Path(f"models/{strategy_id}_model.pkl")
        self.scaler_path = Path(f"models/{strategy_id}_scaler.pkl")
        
        # モデルをロード（存在する場合）
        if self.params['use_pretrained']:
            self._load_model()
    
    def _create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        特徴量を生成
        
        Args:
            df: OHLCVデータフレーム
        
        Returns:
            特徴量データフレーム
        """
        features = pd.DataFrame(index=df.index)
        
        # 基本的な価格変化率
        features['returns_1'] = df['close'].pct_change(1)
        features['returns_5'] = df['close'].pct_change(5)
        features['returns_10'] = df['close'].pct_change(10)
        
        # ボリューム関連
        features['volume_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
        features['volume_change'] = df['volume'].pct_change(1)
        
        # テクニカル指標
        if 'rsi' in df.columns:
            features['rsi'] = df['rsi']
            features['rsi_change'] = df['rsi'].diff(1)
        
        if 'macd' in df.columns:
            features['macd'] = df['macd']
            features['macd_signal'] = df['macd_signal']
            features['macd_hist'] = df['macd_hist']
        
        # ボリンジャーバンド位置
        if 'bb_upper' in df.columns and 'bb_lower' in df.columns:
            bb_width = df['bb_upper'] - df['bb_lower']
            features['bb_position'] = (df['close'] - df['bb_lower']) / bb_width
        
        # 移動平均との乖離
        if 'sma_20' in df.columns:
            features['ma_deviation_20'] = (df['close'] - df['sma_20']) / df['sma_20']
        if 'sma_50' in df.columns:
            features['ma_deviation_50'] = (df['close'] - df['sma_50']) / df['sma_50']
        
        # 高値安値比率
        features['high_low_ratio'] = df['high'] / df['low'] - 1
        features['close_to_high'] = (df['close'] - df['low']) / (df['high'] - df['low'])
        
        # 高度な特徴量（advanced）
        if self.params['feature_set'] == 'advanced':
            # ローリング統計
            for window in [5, 10, 20]:
                features[f'returns_std_{window}'] = df['close'].pct_change().rolling(window).std()
                features[f'volume_std_{window}'] = df['volume'].rolling(window).std()
            
            # 価格の加速度
            features['price_acceleration'] = df['close'].diff().diff()
            
            # サポート・レジスタンスレベル
            features['distance_to_high_20'] = (df['close'] - df['high'].rolling(20).max()) / df['close']
            features['distance_to_low_20'] = (df['close'] - df['low'].rolling(20).min()) / df['close']
        
        # NaNを処理
        features = features.fillna(0)
        
        # 特徴量名を保存
        self.feature_names = features.columns.tolist()
        
        return features
    
    def _create_labels(self, df: pd.DataFrame, lookahead: int = 5) -> pd.Series:
        """
        ラベルを生成（将来の価格変化）
        
        Args:
            df: OHLCVデータフレーム
            lookahead: 先読み期間
        
        Returns:
            ラベル（1: 買い, -1: 売り, 0: ホールド）
        """
        future_returns = df['close'].shift(-lookahead) / df['close'] - 1
        
        # 閾値（1%の変化）
        threshold = 0.01
        
        labels = pd.Series(0, index=df.index)
        labels[future_returns > threshold] = 1    # 買い
        labels[future_returns < -threshold] = -1  # 売り
        
        return labels
    
    def _train_model(self, df: pd.DataFrame) -> None:
        """
        モデルを学習
        
        Args:
            df: OHLCVデータフレーム
        """
        self.logger.info("機械学習モデルの学習を開始")
        
        # 特徴量とラベルを生成
        features = self._create_features(df)
        labels = self._create_labels(df)
        
        # 最後のlookahead分は使用しない（ラベルがないため）
        valid_indices = ~labels.isna()
        X = features[valid_indices]
        y = labels[valid_indices]
        
        # データ分割（最後の20%をバリデーション）
        split_index = int(len(X) * 0.8)
        X_train, X_val = X[:split_index], X[split_index:]
        y_train, y_val = y[:split_index], y[split_index:]
        
        # スケーリング
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)
        
        # モデル学習
        if self.params['model_type'] == 'random_forest':
            self.model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
        
        self.model.fit(X_train_scaled, y_train)
        
        # バリデーション精度
        val_score = self.model.score(X_val_scaled, y_val)
        self.logger.info(f"モデル学習完了 - バリデーション精度: {val_score:.3f}")
        
        # 特徴量重要度
        if hasattr(self.model, 'feature_importances_'):
            importances = pd.DataFrame({
                'feature': self.feature_names,
                'importance': self.model.feature_importances_
            }).sort_values('importance', ascending=False)
            
            self.logger.info("特徴量重要度（上位5つ）:")
            for _, row in importances.head().iterrows():
                self.logger.info(f"  {row['feature']}: {row['importance']:.3f}")
    
    def _save_model(self) -> None:
        """モデルを保存"""
        try:
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(self.model, self.model_path)
            joblib.dump(self.scaler, self.scaler_path)
            self.logger.info("モデルを保存しました")
        except Exception as e:
            self.logger.error(f"モデル保存エラー: {e}")
    
    def _load_model(self) -> None:
        """モデルをロード"""
        try:
            if self.model_path.exists() and self.scaler_path.exists():
                self.model = joblib.load(self.model_path)
                self.scaler = joblib.load(self.scaler_path)
                self.logger.info("モデルをロードしました")
        except Exception as e:
            self.logger.error(f"モデルロードエラー: {e}")
    
    def generate_signal(self, df: pd.DataFrame, current_position: Dict[str, Any], 
                       account_info: Dict[str, Any]) -> Tuple[Signal, Dict[str, Any]]:
        """
        シグナルを生成する
        
        Args:
            df: OHLCVデータフレーム
            current_position: 現在のポジション情報
            account_info: 口座情報
        
        Returns:
            (シグナル, 詳細情報)のタプル
        """
        # データが不足している場合
        if len(df) < self.params['min_data_points']:
            return Signal.HOLD, {'reason': 'データ不足'}
        
        # モデルが未学習または再学習が必要な場合
        if self.model is None or (len(df) - self.last_train_index) > self.params['retrain_interval']:
            self._train_model(df)
            self.last_train_index = len(df)
            # 学習直後は取引しない
            return Signal.HOLD, {'reason': 'モデル学習完了'}
        
        # 特徴量を生成
        features = self._create_features(df)
        latest_features = features.iloc[-1:].values
        
        # 予測
        try:
            latest_features_scaled = self.scaler.transform(latest_features)
            prediction = self.model.predict(latest_features_scaled)[0]
            prediction_proba = self.model.predict_proba(latest_features_scaled)[0]
            
            # 予測確率から信頼度を計算
            if len(prediction_proba) >= 3:  # 3クラス分類の場合
                buy_prob = prediction_proba[np.where(self.model.classes_ == 1)[0][0]]
                sell_prob = prediction_proba[np.where(self.model.classes_ == -1)[0][0]]
                hold_prob = prediction_proba[np.where(self.model.classes_ == 0)[0][0]]
            else:
                buy_prob = sell_prob = hold_prob = 0.33
            
        except Exception as e:
            self.logger.error(f"予測エラー: {e}")
            return Signal.HOLD, {'error': str(e)}
        
        # 詳細情報
        details = {
            'prediction': int(prediction),
            'buy_prob': float(buy_prob),
            'sell_prob': float(sell_prob),
            'hold_prob': float(hold_prob),
            'threshold': self.params['prediction_threshold'],
            'current_price': df['close'].iloc[-1]
        }
        
        # ポジションがある場合
        if current_position and current_position.get('side'):
            # エグジット条件（逆シグナルまたは確信度低下）
            if current_position['side'] == 'LONG' and sell_prob > self.params['prediction_threshold']:
                return Signal.CLOSE_LONG, {**details, 'reason': '売りシグナル検出'}
            elif current_position['side'] == 'SHORT' and buy_prob > self.params['prediction_threshold']:
                return Signal.CLOSE_SHORT, {**details, 'reason': '買いシグナル検出'}
        
        # ポジションがない場合
        else:
            # エントリー条件
            if buy_prob > self.params['prediction_threshold'] and prediction == 1:
                return Signal.BUY, {**details, 'reason': 'ML買いシグナル'}
            elif sell_prob > self.params['prediction_threshold'] and prediction == -1:
                return Signal.SELL, {**details, 'reason': 'ML売りシグナル'}
        
        return Signal.HOLD, details
    
    def calculate_confidence(self, df: pd.DataFrame, signal: Signal) -> float:
        """
        シグナルの確信度を計算
        
        Args:
            df: データフレーム
            signal: シグナル
        
        Returns:
            確信度（0.0〜1.0）
        """
        # 最新の予測確率を確信度として使用
        if hasattr(self, 'last_prediction_proba'):
            if signal == Signal.BUY:
                return self.last_prediction_proba.get('buy_prob', 0.5)
            elif signal == Signal.SELL:
                return self.last_prediction_proba.get('sell_prob', 0.5)
        
        return 0.5
