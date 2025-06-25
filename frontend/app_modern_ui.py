"""
超モダンUI - Chirp Trading System
最新のUIトレンドを取り入れた次世代トレーディングダッシュボード
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
import asyncio
from typing import Dict, Any, Optional, List
import numpy as np
import time
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from backend.gmo_client import GMOCoinClient
from backend.config_manager import get_config_manager
from backend.logger import get_logger

# ページ設定
st.set_page_config(
    page_title="Chirp Network Dashboard",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

def apply_custom_css():
    """カスタムCSS"""
    st.markdown("""
    <style>
        /* フォントのインポート */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        /* 全体のスタイル */
        html, body, [class*="st-"] {
            font-family: 'Inter', sans-serif;
        }

        /* メインの背景色 */
        .stApp {
            background-color: #111111;
            color: #E0E0E0;
        }
        
        /* Streamlitのヘッダーとフッターを非表示 */
        header, footer {
            visibility: hidden;
        }

        /* サイドバー */
        [data-testid="stSidebar"] {
            background-color: #1C1C1C;
            border-right: 1px solid #333333;
            padding: 1.5rem;
        }
        
        /* サイドバーのナビゲーション */
        .sidebar-nav {
            list-style-type: none;
            padding: 0;
            margin: 2rem 0;
        }
        .sidebar-item a {
            display: flex;
            align-items: center;
            padding: 0.8rem 1rem;
            margin: 0.5rem 0;
            border-radius: 8px;
            color: #A0A0A0;
            text-decoration: none;
            transition: background-color 0.2s, color 0.2s;
            font-weight: 500;
        }
        .sidebar-item a:hover {
            background-color: #2A2A2A;
            color: #FFFFFF;
        }
        .sidebar-item.selected a {
            background-color: #333333;
            color: #FFFFFF;
            font-weight: 600;
        }
        .sidebar-item a svg {
            margin-right: 1rem;
            width: 20px;
            height: 20px;
        }

        /* コンテンツエリアのスタイル */
        .main-container {
            background: linear-gradient(180deg, rgba(28, 28, 28, 0.9) 0%, #111111 100%);
            padding: 2rem;
            border-radius: 12px;
        }
        
        /* カード風コンテナ */
        .metric-card {
            background-color: #1C1C1C;
            padding: 1.5rem;
            border-radius: 10px;
            border: 1px solid #282828;
            height: 100%;
        }

        /* セクションタイトル */
        h1, h2, h3 {
            color: #FFFFFF;
            font-weight: 600;
        }
        h3 {
            font-size: 1.25rem;
            border-bottom: 1px solid #282828;
            padding-bottom: 0.75rem;
            margin-bottom: 1rem;
        }

        /* ボタン */
        .stButton>button {
            background: linear-gradient(90deg, #FF9900, #FF7700);
            color: white;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        .stButton>button:hover {
            box-shadow: 0 0 15px rgba(255, 153, 0, 0.5);
            transform: translateY(-2px);
        }
        
        /* データフレームのヘッダー */
        .stDataFrame .col_heading {
            background-color: #2A2A2A !important;
        }

    </style>
    """, unsafe_allow_html=True)

def create_header():
    """モダンなヘッダー"""
    st.markdown("""
    <div class="main-header">
        <h1 class="main-title floating">🚀 CHIRP</h1>
        <p class="main-subtitle glow-text">Next-Gen Trading Dashboard</p>
    </div>
    """, unsafe_allow_html=True)

def create_navigation():
    """モダンなナビゲーション"""
    if 'active_page' not in st.session_state:
        st.session_state.active_page = 'Dashboard'
    
    pages = ['Dashboard', 'Portfolio', 'Trading', 'Analytics', 'Settings']
    
    cols = st.columns(len(pages))
    for i, (col, page) in enumerate(zip(cols, pages)):
        with col:
            if st.button(f"📊 {page}" if page == 'Dashboard' 
                        else f"💼 {page}" if page == 'Portfolio'
                        else f"📈 {page}" if page == 'Trading'
                        else f"📊 {page}" if page == 'Analytics'
                        else f"⚙️ {page}", 
                        key=f"nav_{page}",
                        use_container_width=True):
                st.session_state.active_page = page
                st.rerun()

def create_metrics_grid(data):
    """美しいメトリクスグリッド"""
    total_balance = data.get('balance', {}).get('total_jpy', 0)
    total_pnl = data.get('performance', {}).get('total_pnl', 0)
    win_rate = data.get('performance', {}).get('win_rate', 0)
    total_trades = data.get('performance', {}).get('total_trades', 0)
    
    st.markdown("""
    <div class="metric-grid">
        <div class="modern-card metric-item hover-scale">
            <div class="metric-value pulse">¥{:,.0f}</div>
            <div class="metric-label">Total Balance</div>
            <div class="metric-change positive">+12.5%</div>
        </div>
        <div class="modern-card metric-item hover-scale">
            <div class="metric-value">¥{:,.0f}</div>
            <div class="metric-label">P&L Today</div>
            <div class="metric-change {}">{}%</div>
        </div>
        <div class="modern-card metric-item hover-scale">
            <div class="metric-value">{:.1f}%</div>
            <div class="metric-label">Win Rate</div>
            <div class="metric-change positive">+2.1%</div>
        </div>
        <div class="modern-card metric-item hover-scale">
            <div class="metric-value">{}</div>
            <div class="metric-label">Total Trades</div>
            <div class="metric-change positive">+5</div>
        </div>
    </div>
    """.format(
        total_balance,
        total_pnl,
        "positive" if total_pnl >= 0 else "negative",
        f"+{total_pnl/total_balance*100:.2f}" if total_pnl >= 0 else f"{total_pnl/total_balance*100:.2f}",
        win_rate,
        total_trades
    ), unsafe_allow_html=True)

def create_modern_chart(data):
    """超モダンなチャート"""
    # サンプルデータ生成
    dates = pd.date_range(start=datetime.now() - timedelta(days=30), end=datetime.now(), freq='H')
    prices = 5000000 + np.cumsum(np.random.randn(len(dates)) * 10000)
    
    fig = go.Figure()
    
    # メインライン（グラデーション）
    fig.add_trace(go.Scatter(
        x=dates,
        y=prices,
        mode='lines',
        name='Price',
        line=dict(color='rgba(255, 107, 107, 0.8)', width=3),
        fill='tonexty',
        fillcolor='rgba(255, 107, 107, 0.1)'
    ))
    
    # 移動平均
    ma_20 = pd.Series(prices).rolling(20).mean()
    fig.add_trace(go.Scatter(
        x=dates,
        y=ma_20,
        mode='lines',
        name='MA 20',
        line=dict(color='rgba(78, 205, 196, 0.8)', width=2, dash='dash')
    ))
    
    fig.update_layout(
        title="BTC/JPY - Real-time Price Action",
        template="plotly_dark",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Inter", color="white"),
        title_font_size=20,
        title_font_color="white",
        xaxis=dict(
            showgrid=True,
            gridcolor='rgba(255, 255, 255, 0.1)',
            zeroline=False
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(255, 255, 255, 0.1)',
            zeroline=False
        ),
        legend=dict(
            bgcolor='rgba(255, 255, 255, 0.1)',
            bordercolor='rgba(255, 255, 255, 0.2)',
            borderwidth=1
        ),
        height=400
    )
    
    return fig

def create_portfolio_overview(data):
    """ポートフォリオ概要"""
    assets = data.get('balance', {}).get('assets', [])
    
    if assets:
        # ドーナツチャート
        fig = go.Figure(data=[go.Pie(
            labels=[a['symbol'] for a in assets],
            values=[a['jpy_value'] for a in assets],
            hole=.6,
            marker=dict(
                colors=['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#feca57'],
                line=dict(color='rgba(255, 255, 255, 0.2)', width=2)
            )
        )])
        
        fig.update_layout(
            title="Portfolio Distribution",
            template="plotly_dark",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family="Inter", color="white"),
            showlegend=True,
            height=300
        )
        
        return fig
    return None

def dashboard_page(data):
    """ダッシュボードページ"""
    create_metrics_grid(data)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown('<div class="glass-container">', unsafe_allow_html=True)
        st.plotly_chart(create_modern_chart(data), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="glass-container">', unsafe_allow_html=True)
        portfolio_chart = create_portfolio_overview(data)
        if portfolio_chart:
            st.plotly_chart(portfolio_chart, use_container_width=True)
        else:
            st.info("No portfolio data available")
        st.markdown('</div>', unsafe_allow_html=True)

def portfolio_page(data):
    """ポートフォリオページ"""
    st.markdown('<div class="glass-container">', unsafe_allow_html=True)
    st.markdown("## 💼 Portfolio Overview")
    
    positions = data.get('positions', [])
    if positions:
        df = pd.DataFrame(positions)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No positions found")
    st.markdown('</div>', unsafe_allow_html=True)

def trading_page(data):
    """トレーディングページ"""
    st.markdown('<div class="glass-container">', unsafe_allow_html=True)
    st.markdown("## 📈 Trading History")
    
    trades = data.get('trades', [])
    if trades:
        df = pd.DataFrame(trades)
        st.dataframe(df.head(20), use_container_width=True)
    else:
        st.info("No trades found")
    st.markdown('</div>', unsafe_allow_html=True)

def analytics_page(data):
    """分析ページ"""
    st.markdown('<div class="glass-container">', unsafe_allow_html=True)
    st.markdown("## 📊 Analytics Dashboard")
    st.info("Advanced analytics coming soon...")
    st.markdown('</div>', unsafe_allow_html=True)

def settings_page(data):
    """設定ページ"""
    st.markdown('<div class="glass-container">', unsafe_allow_html=True)
    st.markdown("## ⚙️ System Settings")
    
    # API状態
    st.success("✅ API Connection: Active")
    
    # 設定オプション
    st.slider("Refresh Interval", 10, 300, 30)
    st.checkbox("Enable Notifications")
    st.checkbox("Dark Mode", value=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def get_mock_data():
    """モックデータ生成"""
    np.random.seed(42)
    assets = [
        {'symbol': 'BTC', 'name': 'Köterberg, Miner', 'office': 'NaheinsOffice', 'amount': 0.5, 'jpy_value': 5000000, 'status': 'online'},
        {'symbol': 'ETH', 'name': 'Tim\'s MM, Miner', 'office': 'NaheinsOffice', 'amount': 10, 'jpy_value': 3000000, 'status': 'online'},
        {'symbol': 'XRP', 'name': 'Demo, Miner', 'office': 'NaheinsOffice', 'amount': 5000, 'jpy_value': 250000, 'status': 'offline'},
        {'symbol': 'LTC', 'name': 'Köterberg, Miner', 'office': 'NaheinsOffice', 'amount': 50, 'jpy_value': 400000, 'status': 'online'},
        {'symbol': 'DOGE', 'name': 'Tim\'s MM, Miner', 'office': 'NaheinsOffice', 'amount': 100000, 'jpy_value': 120000, 'status': 'warning'},
    ]
    total_jpy = sum(a['jpy_value'] for a in assets) + 1500000 # JPY残高
    
    trades = []
    for _ in range(50):
        trades.append({
            'timestamp': datetime.now() - timedelta(days=np.random.randint(1, 30)),
            'symbol': np.random.choice(['BTC_JPY', 'ETH_JPY', 'XRP_JPY']),
            'side': np.random.choice(['BUY', 'SELL']),
            'size': np.random.uniform(0.01, 1.0),
            'price': np.random.uniform(3000000, 7000000),
            'fee': np.random.uniform(100, 1000),
            'orderId': f'order_{np.random.randint(10000, 99999)}'
        })

    return {
        'balance': {'total_jpy': total_jpy, 'assets': assets},
        'positions': assets, # このUIではポジションと資産を同一視
        'trades': trades,
        'performance': {
            'total_pnl': 356000, 'win_rate': 62.5, 'total_trades': 128
        },
        'pings': {'transmitted': 408, 'received': 2003},
        'last_update': datetime.now()
    }

def main():
    """メインアプリケーション"""
    apply_custom_css()
    
    # ヘッダー
    create_header()
    
    # ナビゲーション
    create_navigation()
    
    # データ取得
    data = get_mock_data()
    
    # ページ表示
    page = st.session_state.get('active_page', 'Dashboard')
    
    if page == 'Dashboard':
        dashboard_page(data)
    elif page == 'Portfolio':
        portfolio_page(data)
    elif page == 'Trading':
        trading_page(data)
    elif page == 'Analytics':
        analytics_page(data)
    elif page == 'Settings':
        settings_page(data)

if __name__ == "__main__":
    main() 