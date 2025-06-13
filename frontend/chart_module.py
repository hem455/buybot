"""
チャート機能強化版 - モダンUI

リアルタイムチャートとテクニカル指標表示
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import asyncio
import json

# バックエンドモジュールのインポート
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from backend.data_fetcher import GMOCoinRESTFetcher, DataStorage
from backend.indicator import IndicatorCalculator
from backend.config_manager import get_config_manager
from backend.logger import get_logger


class ChartManager:
    """チャート管理クラス"""
    
    def __init__(self):
        self.config = get_config_manager()
        self.logger = get_logger()
        self.storage = DataStorage(self.config)
        self.indicator_calc = IndicatorCalculator()
        self.rest_fetcher = GMOCoinRESTFetcher()
    
    async def load_chart_data(self, symbol: str, interval: str, days: int = 30) -> pd.DataFrame:
        """チャートデータをロード"""
        try:
            # ローカルストレージから読み込み
            df = self.storage.load_ohlcv(
                symbol, 
                interval,
                datetime.now() - timedelta(days=days),
                datetime.now()
            )
            
            if df.empty:
                self.logger.warning(f"ローカルデータが見つかりません: {symbol} {interval}")
                # APIから取得を試みる
                async with self.rest_fetcher as fetcher:
                    df = await fetcher.fetch_ohlcv(symbol, interval, limit=500)
            
            # 指標を計算
            if not df.empty:
                df = self.indicator_calc.calculate_all(df)
            
            return df
            
        except Exception as e:
            self.logger.error(f"チャートデータ読み込みエラー: {e}")
            # デモデータを返す
            return self._generate_demo_data(days)
    
    def _generate_demo_data(self, days: int) -> pd.DataFrame:
        """デモデータ生成"""
        dates = pd.date_range(end=datetime.now(), periods=days*24, freq='H')
        
        # リアルな価格変動をシミュレート
        price = 6500000  # 初期価格
        prices = []
        volumes = []
        
        for _ in range(len(dates)):
            # ランダムウォーク
            change = np.random.normal(0, 0.002)
            price = price * (1 + change)
            prices.append(price)
            volumes.append(np.random.uniform(10, 100))
        
        # OHLCVデータ作成
        df = pd.DataFrame({
            'timestamp': dates,
            'open': prices,
            'high': [p * (1 + abs(np.random.normal(0, 0.001))) for p in prices],
            'low': [p * (1 - abs(np.random.normal(0, 0.001))) for p in prices],
            'close': [p * (1 + np.random.normal(0, 0.0005)) for p in prices],
            'volume': volumes
        })
        
        df.set_index('timestamp', inplace=True)
        
        # 指標を計算
        df = self.indicator_calc.calculate_all(df)
        
        return df
    
    def create_main_chart(self, df: pd.DataFrame, symbol: str, 
                         indicators: List[str] = None,
                         chart_type: str = 'candlestick') -> go.Figure:
        """メインチャート作成"""
        
        # サブプロット作成（メインチャート + ボリューム + 指標）
        subplot_rows = 3 if indicators else 2
        row_heights = [0.6, 0.2, 0.2] if indicators else [0.7, 0.3]
        
        fig = make_subplots(
            rows=subplot_rows,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=row_heights,
            subplot_titles=(f'{symbol} Price', 'Volume', 'Indicators' if indicators else '')
        )
        
        # カラーテーマ
        colors = {
            'up': '#00d4aa',
            'down': '#ff4757',
            'ma_fast': '#ff6b35',
            'ma_slow': '#45b7d1',
            'volume': 'rgba(255, 107, 53, 0.3)',
            'grid': 'rgba(45, 49, 57, 0.3)'
        }
        
        # メインチャート（ローソク足またはライン）
        if chart_type == 'candlestick':
            fig.add_trace(
                go.Candlestick(
                    x=df.index,
                    open=df['open'],
                    high=df['high'],
                    low=df['low'],
                    close=df['close'],
                    name='Price',
                    increasing_line_color=colors['up'],
                    decreasing_line_color=colors['down'],
                    increasing_fillcolor=colors['up'],
                    decreasing_fillcolor=colors['down']
                ),
                row=1, col=1
            )
        else:  # line chart
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['close'],
                    mode='lines',
                    name='Close Price',
                    line=dict(color=colors['up'], width=2)
                ),
                row=1, col=1
            )
        
        # 移動平均線
        if 'sma_20' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['sma_20'],
                    mode='lines',
                    name='SMA 20',
                    line=dict(color=colors['ma_fast'], width=1.5)
                ),
                row=1, col=1
            )
        
        if 'sma_50' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['sma_50'],
                    mode='lines',
                    name='SMA 50',
                    line=dict(color=colors['ma_slow'], width=1.5)
                ),
                row=1, col=1
            )
        
        # ボリンジャーバンド
        if all(col in df.columns for col in ['bb_upper', 'bb_middle', 'bb_lower']):
            # 上部バンド
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['bb_upper'],
                    mode='lines',
                    name='BB Upper',
                    line=dict(color='rgba(255, 255, 255, 0.3)', width=1, dash='dash')
                ),
                row=1, col=1
            )
            
            # 下部バンド
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['bb_lower'],
                    mode='lines',
                    name='BB Lower',
                    line=dict(color='rgba(255, 255, 255, 0.3)', width=1, dash='dash'),
                    fill='tonexty',
                    fillcolor='rgba(255, 255, 255, 0.05)'
                ),
                row=1, col=1
            )
        
        # ボリューム
        colors_volume = ['red' if df['close'].iloc[i] < df['open'].iloc[i] else 'green' 
                        for i in range(len(df))]
        
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df['volume'],
                name='Volume',
                marker_color=colors_volume,
                marker_line_width=0,
                opacity=0.5
            ),
            row=2, col=1
        )
        
        # 指標（RSI、MACDなど）
        if indicators and subplot_rows > 2:
            if 'RSI' in indicators and 'rsi' in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df.index,
                        y=df['rsi'],
                        mode='lines',
                        name='RSI',
                        line=dict(color='#6c5ce7', width=2)
                    ),
                    row=3, col=1
                )
                
                # RSIの基準線
                fig.add_hline(y=70, line_color='rgba(255, 71, 87, 0.5)', 
                            line_width=1, line_dash='dash', row=3, col=1)
                fig.add_hline(y=30, line_color='rgba(0, 212, 170, 0.5)', 
                            line_width=1, line_dash='dash', row=3, col=1)
            
            elif 'MACD' in indicators and all(col in df.columns for col in ['macd', 'macd_signal']):
                # MACD
                fig.add_trace(
                    go.Scatter(
                        x=df.index,
                        y=df['macd'],
                        mode='lines',
                        name='MACD',
                        line=dict(color='#45b7d1', width=2)
                    ),
                    row=3, col=1
                )
                
                # シグナル線
                fig.add_trace(
                    go.Scatter(
                        x=df.index,
                        y=df['macd_signal'],
                        mode='lines',
                        name='Signal',
                        line=dict(color='#ff6b35', width=2)
                    ),
                    row=3, col=1
                )
                
                # ヒストグラム
                if 'macd_hist' in df.columns:
                    colors_hist = ['#00d4aa' if val > 0 else '#ff4757' 
                                  for val in df['macd_hist']]
                    
                    fig.add_trace(
                        go.Bar(
                            x=df.index,
                            y=df['macd_hist'],
                            name='MACD Hist',
                            marker_color=colors_hist,
                            marker_line_width=0
                        ),
                        row=3, col=1
                    )
        
        # レイアウト設定
        fig.update_layout(
            template="plotly_dark",
            title=dict(
                text=f"{symbol} - {df.index[-1].strftime('%Y-%m-%d %H:%M')}",
                font=dict(size=20, color='#fafafa')
            ),
            paper_bgcolor='rgba(26, 29, 36, 1)',
            plot_bgcolor='rgba(26, 29, 36, 1)',
            height=700,
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor='rgba(26, 29, 36, 0.8)'
            ),
            hovermode='x unified',
            margin=dict(l=70, r=70, t=50, b=50)
        )
        
        # X軸設定（最下部のみ表示）
        fig.update_xaxes(
            showgrid=True,
            gridcolor=colors['grid'],
            rangeslider_visible=False,
            row=subplot_rows, col=1
        )
        
        # Y軸設定
        fig.update_yaxes(
            showgrid=True,
            gridcolor=colors['grid'],
            title_text="Price (¥)",
            row=1, col=1
        )
        
        fig.update_yaxes(
            showgrid=True,
            gridcolor=colors['grid'],
            title_text="Volume",
            row=2, col=1
        )
        
        if subplot_rows > 2:
            if 'RSI' in indicators:
                fig.update_yaxes(
                    showgrid=True,
                    gridcolor=colors['grid'],
                    title_text="RSI",
                    range=[0, 100],
                    row=3, col=1
                )
            elif 'MACD' in indicators:
                fig.update_yaxes(
                    showgrid=True,
                    gridcolor=colors['grid'],
                    title_text="MACD",
                    row=3, col=1
                )
        
        return fig
    
    def create_mini_price_chart(self, df: pd.DataFrame, height: int = 200) -> go.Figure:
        """ミニ価格チャート"""
        fig = go.Figure()
        
        # 価格ライン
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['close'],
                mode='lines',
                fill='tozeroy',
                fillcolor='rgba(255, 107, 53, 0.1)',
                line=dict(color='#ff6b35', width=2),
                showlegend=False
            )
        )
        
        # 最新価格をマーク
        fig.add_trace(
            go.Scatter(
                x=[df.index[-1]],
                y=[df['close'].iloc[-1]],
                mode='markers+text',
                marker=dict(size=8, color='#ff6b35'),
                text=[f"¥{df['close'].iloc[-1]:,.0f}"],
                textposition='top right',
                showlegend=False
            )
        )
        
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor='rgba(26, 29, 36, 1)',
            plot_bgcolor='rgba(26, 29, 36, 1)',
            height=height,
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis=dict(showgrid=False, showticklabels=False),
            yaxis=dict(showgrid=False, showticklabels=False)
        )
        
        return fig
    
    def create_depth_chart(self, orderbook: Dict[str, Any]) -> go.Figure:
        """板情報の深度チャート"""
        fig = go.Figure()
        
        if not orderbook or 'asks' not in orderbook or 'bids' not in orderbook:
            return fig
        
        # 買い注文（Bids）
        bids = orderbook['bids']
        bid_prices = [b[0] for b in bids]
        bid_volumes = [b[1] for b in bids]
        bid_cumulative = np.cumsum(bid_volumes)
        
        # 売り注文（Asks）
        asks = orderbook['asks']
        ask_prices = [a[0] for a in asks]
        ask_volumes = [a[1] for a in asks]
        ask_cumulative = np.cumsum(ask_volumes)
        
        # Bidsプロット
        fig.add_trace(
            go.Scatter(
                x=bid_prices,
                y=bid_cumulative,
                mode='lines',
                fill='tozeroy',
                fillcolor='rgba(0, 212, 170, 0.3)',
                line=dict(color='#00d4aa', width=2),
                name='Bids'
            )
        )
        
        # Asksプロット
        fig.add_trace(
            go.Scatter(
                x=ask_prices,
                y=ask_cumulative,
                mode='lines',
                fill='tozeroy',
                fillcolor='rgba(255, 71, 87, 0.3)',
                line=dict(color='#ff4757', width=2),
                name='Asks'
            )
        )
        
        fig.update_layout(
            template="plotly_dark",
            title="Order Book Depth",
            paper_bgcolor='rgba(26, 29, 36, 1)',
            plot_bgcolor='rgba(26, 29, 36, 1)',
            height=300,
            xaxis_title="Price (¥)",
            yaxis_title="Cumulative Volume",
            hovermode='x'
        )
        
        return fig


# チャート表示用の関数
def render_trading_chart(symbol: str = "BTC_JPY", interval: str = "1hour", 
                        indicators: List[str] = None):
    """トレーディングチャートを表示"""
    
    # チャートマネージャー
    chart_manager = ChartManager()
    
    # 非同期でデータ取得
    @st.cache_data(ttl=60)  # 60秒キャッシュ
    def load_data():
        return asyncio.run(chart_manager.load_chart_data(symbol, interval))
    
    # データ読み込み
    with st.spinner(f"Loading {symbol} data..."):
        df = load_data()
    
    if df.empty:
        st.error("データの読み込みに失敗しました")
        return
    
    # チャートタイプ選択
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        chart_type = st.radio(
            "Chart Type",
            ["Candlestick", "Line"],
            horizontal=True,
            index=0
        )
    
    with col2:
        show_bb = st.checkbox("Bollinger Bands", value=True)
    
    with col3:
        show_volume = st.checkbox("Volume", value=True)
    
    with col4:
        indicator = st.selectbox(
            "Indicator",
            ["None", "RSI", "MACD"],
            index=1
        )
    
    # インジケーターリスト
    indicators = [indicator] if indicator != "None" else None
    
    # チャート作成
    fig = chart_manager.create_main_chart(
        df,
        symbol,
        indicators=indicators,
        chart_type=chart_type.lower()
    )
    
    # チャート表示
    st.plotly_chart(fig, use_container_width=True)
    
    # 統計情報
    col1, col2, col3, col4 = st.columns(4)
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    with col1:
        change = ((latest['close'] - prev['close']) / prev['close']) * 100
        st.metric(
            "Last Price",
            f"¥{latest['close']:,.0f}",
            f"{change:+.2f}%"
        )
    
    with col2:
        st.metric(
            "24h High",
            f"¥{df['high'].tail(24).max():,.0f}"
        )
    
    with col3:
        st.metric(
            "24h Low",
            f"¥{df['low'].tail(24).min():,.0f}"
        )
    
    with col4:
        st.metric(
            "24h Volume",
            f"{df['volume'].tail(24).sum():,.0f}"
        )
