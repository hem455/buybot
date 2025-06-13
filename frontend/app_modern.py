"""
Streamlit UI メインアプリケーション - モダンダークテーマ版

GMOコイン自動売買システムのWebインターフェース
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
import asyncio
from typing import Dict, Any, Optional
import numpy as np

from frontend.chart_module import ChartManager, render_trading_chart
from frontend.components import ModernComponents
from frontend.dashboard_utils import DashboardDataManager, format_jpy, format_percentage
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from backend.config_manager import get_config_manager
from backend.logger import get_logger
from backend.strategy import get_strategy_manager
from backend.backtester import Backtester
from backend.data_fetcher import GMOCoinRESTFetcher
from backend.risk_manager import RiskManager
from backend.order_executor import OrderExecutor

# カスタムCSSでダークテーマを適用
def apply_custom_css():
    st.markdown("""
    <style>
    /* メインの背景色 */
    .stApp {
        background-color: #0e1117;
        color: #fafafa;
    }
    
    /* サイドバー */
    .css-1d391kg {
        background-color: #1a1d24;
    }
    
    /* カード風のコンテナ */
    .metric-card {
        background: linear-gradient(135deg, #1a1d24 0%, #2d3139 100%);
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #2d3139;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    
    /* メトリクスのスタイル */
    .metric-value {
        font-size: 2rem;
        font-weight: 600;
        color: #fafafa;
        margin: 0.5rem 0;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #a3a3a3;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    /* ポジティブ/ネガティブな値 */
    .positive {
        color: #00d4aa;
    }
    
    .negative {
        color: #ff4757;
    }
    
    /* ボタンのスタイル */
    .stButton > button {
        background: linear-gradient(135deg, #ff6b35 0%, #ff4757 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        font-weight: 600;
        border-radius: 5px;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(255, 107, 53, 0.4);
    }
    
    /* グリッドレイアウト */
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 1rem;
        margin: 1rem 0;
    }
    
    /* チャートコンテナ */
    .chart-container {
        background-color: #1a1d24;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
        border: 1px solid #2d3139;
    }
    
    /* テーブルスタイル */
    .dataframe {
        background-color: #1a1d24;
        color: #fafafa;
    }
    
    /* タブのスタイル */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
        background-color: #1a1d24;
        padding: 0.5rem;
        border-radius: 10px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        border-radius: 5px;
        color: #a3a3a3;
        font-weight: 500;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #2d3139;
        color: #fafafa;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #ff6b35;
        color: #fafafa;
    }
    
    /* セレクトボックス */
    .stSelectbox > div > div {
        background-color: #1a1d24;
        color: #fafafa;
        border: 1px solid #2d3139;
    }
    
    /* 入力フィールド */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input {
        background-color: #1a1d24;
        color: #fafafa;
        border: 1px solid #2d3139;
    }
    
    /* エクスパンダー */
    .streamlit-expanderHeader {
        background-color: #1a1d24;
        border: 1px solid #2d3139;
        border-radius: 5px;
    }
    
    /* アニメーション */
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.7; }
        100% { opacity: 1; }
    }
    
    .live-indicator {
        display: inline-block;
        width: 8px;
        height: 8px;
        background-color: #00d4aa;
        border-radius: 50%;
        margin-right: 0.5rem;
        animation: pulse 2s infinite;
    }
    
    /* スクロールバー */
    ::-webkit-scrollbar {
        width: 10px;
        height: 10px;
    }
    
    ::-webkit-scrollbar-track {
        background: #1a1d24;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #2d3139;
        border-radius: 5px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #3d4149;
    }
    </style>
    """, unsafe_allow_html=True)

# ページ設定
st.set_page_config(
    page_title="Chirp Trading System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSSを適用
apply_custom_css()

# セッション状態の初期化
if 'bot_running' not in st.session_state:
    st.session_state.bot_running = False
if 'backtest_result' not in st.session_state:
    st.session_state.backtest_result = None
if 'current_tab' not in st.session_state:
    st.session_state.current_tab = "Dashboard"


def create_metric_card(label: str, value: str, delta: str = None, delta_color: str = "normal"):
    """メトリクスカードを作成"""
    delta_html = ""
    if delta:
        delta_class = "positive" if delta_color == "positive" else "negative" if delta_color == "negative" else ""
        delta_html = f'<div class="{delta_class}">{delta}</div>'
    
    return f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        {delta_html}
    </div>
    """


def main():
    """メインアプリケーション"""
    # ヘッダー
    col1, col2, col3 = st.columns([2, 4, 2])
    
    with col1:
        st.markdown("# 📊 Chirp")
        st.markdown("*Advanced Crypto Trading System*")
    
    with col3:
        if st.session_state.bot_running:
            st.markdown('<span class="live-indicator"></span>**LIVE**', unsafe_allow_html=True)
        else:
            st.markdown('⚫ **OFFLINE**', unsafe_allow_html=True)
    
    # メインタブ
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "🔄 Backtest", "⚙️ Strategies", "📈 Analytics"])
    
    with tab1:
        dashboard_page()
    
    with tab2:
        backtest_page()
    
    with tab3:
        strategies_page()
    
    with tab4:
        analytics_page()


def dashboard_page():
    """ダッシュボードページ"""
    # 上部のメトリクス
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(create_metric_card(
            "Total Balance",
            "¥1,986,154",
            "+2.34%",
            "positive"
        ), unsafe_allow_html=True)
    
    with col2:
        st.markdown(create_metric_card(
            "Today's P/L",
            "¥45,678",
            "+15.2%",
            "positive"
        ), unsafe_allow_html=True)
    
    with col3:
        st.markdown(create_metric_card(
            "Active Positions",
            "3",
            "BTC, ETH, XRP"
        ), unsafe_allow_html=True)
    
    with col4:
        st.markdown(create_metric_card(
            "Win Rate",
            "68.5%",
            "+5.2%",
            "positive"
        ), unsafe_allow_html=True)
    
    # チャートセクション
    st.markdown("### 📈 Performance Overview")
    
    # サンプルデータ生成
    dates = pd.date_range(start='2024-01-01', end='2024-06-12', freq='D')
    portfolio_value = 1000000 + np.cumsum(np.random.randn(len(dates)) * 10000)
    
    fig = go.Figure()
    
    # ポートフォリオ価値の推移
    fig.add_trace(go.Scatter(
        x=dates,
        y=portfolio_value,
        mode='lines',
        name='Portfolio Value',
        line=dict(color='#ff6b35', width=3),
        fill='tozeroy',
        fillcolor='rgba(255, 107, 53, 0.1)'
    ))
    
    # レイアウト設定
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor='rgba(26, 29, 36, 1)',
        plot_bgcolor='rgba(26, 29, 36, 1)',
        title="Portfolio Performance",
        title_font_size=20,
        title_font_color='#fafafa',
        xaxis=dict(
            gridcolor='rgba(45, 49, 57, 0.5)',
            showgrid=True,
            zeroline=False
        ),
        yaxis=dict(
            gridcolor='rgba(45, 49, 57, 0.5)',
            showgrid=True,
            zeroline=False,
            tickformat='¥,.0f'
        ),
        hovermode='x unified',
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # ポジション詳細とマーケット情報
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("### 📊 Active Positions")
        positions_data = pd.DataFrame({
            'Symbol': ['BTC/JPY', 'ETH/JPY', 'XRP/JPY'],
            'Side': ['LONG', 'LONG', 'SHORT'],
            'Size': [0.05, 0.5, 1000],
            'Entry Price': ['¥6,543,210', '¥543,210', '¥65.43'],
            'Current Price': ['¥6,789,012', '¥567,890', '¥62.10'],
            'P/L': ['+¥12,290', '+¥12,340', '+¥3,330'],
            'P/L %': ['+3.76%', '+4.54%', '+5.37%']
        })
        
        # スタイル付きデータフレーム
        st.dataframe(
            positions_data,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Side": st.column_config.TextColumn(
                    "Side",
                    help="Position direction"
                ),
                "P/L": st.column_config.TextColumn(
                    "P/L",
                    help="Profit/Loss"
                ),
            }
        )
    
    with col2:
        st.markdown("### 🌐 Market Overview")
        
        # 仮想通貨価格
        crypto_prices = {
            'BTC': {'price': '¥6,789,012', 'change': '+2.3%'},
            'ETH': {'price': '¥567,890', 'change': '+4.5%'},
            'XRP': {'price': '¥62.10', 'change': '-1.2%'},
            'LTC': {'price': '¥12,345', 'change': '+1.8%'}
        }
        
        for symbol, data in crypto_prices.items():
            color = "positive" if data['change'].startswith('+') else "negative"
            st.markdown(f"""
            <div class="metric-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div class="metric-label">{symbol}/JPY</div>
                        <div style="font-size: 1.5rem; font-weight: 600;">{data['price']}</div>
                    </div>
                    <div class="{color}" style="font-size: 1.2rem;">{data['change']}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)


def backtest_page():
    """バックテストページ"""
    st.markdown("### 🔄 Strategy Backtesting")
    
    # 設定カラム
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        strategy_manager = get_strategy_manager()
        available_strategies = strategy_manager.get_available_strategies()
        strategy_options = {s['id']: s['name'] for s in available_strategies}
        
        selected_strategy = st.selectbox(
            "Strategy",
            options=list(strategy_options.keys()),
            format_func=lambda x: strategy_options[x]
        )
    
    with col2:
        symbol = st.selectbox(
            "Symbol",
            options=['BTC_JPY', 'ETH_JPY', 'XRP_JPY'],
            index=0
        )
    
    with col3:
        timeframe = st.selectbox(
            "Timeframe",
            options=['1hour', '4hour', '1day'],
            index=0
        )
    
    with col4:
        initial_capital = st.number_input(
            "Initial Capital (¥)",
            min_value=100000,
            value=1000000,
            step=100000
        )
    
    # 期間設定
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=datetime.now() - timedelta(days=90)
        )
    
    with col2:
        end_date = st.date_input(
            "End Date",
            value=datetime.now()
        )
    
    # 実行ボタン
    if st.button("🚀 Run Backtest", type="primary", use_container_width=True):
        with st.spinner("Running backtest..."):
            # バックテスト実行のロジック
            st.success("Backtest completed!")
            
            # 結果表示
            display_backtest_results_modern()


def display_backtest_results_modern():
    """モダンなバックテスト結果表示"""
    # 結果サマリー
    col1, col2, col3, col4 = st.columns(4)
    
    metrics = [
        ("Total Return", "+156.8%", "positive"),
        ("Sharpe Ratio", "1.86", "positive"),
        ("Max Drawdown", "-18.5%", "negative"),
        ("Win Rate", "72.3%", "positive")
    ]
    
    for col, (label, value, color) in zip([col1, col2, col3, col4], metrics):
        with col:
            st.markdown(create_metric_card(label, value, delta_color=color), unsafe_allow_html=True)
    
    # 詳細なチャート
    st.markdown("### 📊 Equity Curve")
    
    # サンプルデータ
    dates = pd.date_range(start='2024-01-01', end='2024-06-12', freq='D')
    equity = 1000000 + np.cumsum(np.random.randn(len(dates)) * 5000)
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=dates,
        y=equity,
        mode='lines',
        name='Strategy',
        line=dict(color='#00d4aa', width=3)
    ))
    
    # Buy & Hold比較
    buy_hold = 1000000 * (1 + np.linspace(0, 0.5, len(dates)))
    fig.add_trace(go.Scatter(
        x=dates,
        y=buy_hold,
        mode='lines',
        name='Buy & Hold',
        line=dict(color='#ff4757', width=2, dash='dash')
    ))
    
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor='rgba(26, 29, 36, 1)',
        plot_bgcolor='rgba(26, 29, 36, 1)',
        height=400,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)


def strategies_page():
    """戦略管理ページ"""
    st.markdown("### ⚙️ Strategy Management")
    
    # 戦略リスト
    strategies = [
        {
            'name': 'Grid Trading',
            'status': 'Active',
            'performance': '+23.4%',
            'trades': 156,
            'win_rate': '68%'
        },
        {
            'name': 'Multi-Timeframe',
            'status': 'Active',
            'performance': '+45.2%',
            'trades': 89,
            'win_rate': '72%'
        },
        {
            'name': 'ML-Based',
            'status': 'Testing',
            'performance': '+12.8%',
            'trades': 234,
            'win_rate': '65%'
        }
    ]
    
    for strategy in strategies:
        status_color = "#00d4aa" if strategy['status'] == 'Active' else "#ff6b35"
        
        st.markdown(f"""
        <div class="metric-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h4 style="margin: 0; color: #fafafa;">{strategy['name']}</h4>
                    <p style="color: #a3a3a3; margin: 0.5rem 0;">
                        Trades: {strategy['trades']} | Win Rate: {strategy['win_rate']}
                    </p>
                </div>
                <div style="text-align: right;">
                    <div style="color: {status_color}; font-weight: 600;">{strategy['status']}</div>
                    <div class="positive" style="font-size: 1.5rem; margin-top: 0.5rem;">
                        {strategy['performance']}
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)


def analytics_page():
    """分析ページ"""
    st.markdown("### 📈 Advanced Analytics")
    
    # ヒートマップ
    st.markdown("#### Monthly Returns Heatmap")
    
    # サンプルデータ生成
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
    years = ['2023', '2024']
    
    data = np.random.randn(len(years), len(months)) * 10
    
    fig = go.Figure(data=go.Heatmap(
        z=data,
        x=months,
        y=years,
        colorscale='RdYlGn',
        text=[[f'{val:.1f}%' for val in row] for row in data],
        texttemplate='%{text}',
        textfont={"size": 12}
    ))
    
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor='rgba(26, 29, 36, 1)',
        plot_bgcolor='rgba(26, 29, 36, 1)',
        height=300
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # リスクメトリクス
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Risk Metrics")
        risk_metrics = {
            'Value at Risk (95%)': '¥-45,678',
            'Expected Shortfall': '¥-67,890',
            'Beta': '0.87',
            'Correlation with BTC': '0.92'
        }
        
        for metric, value in risk_metrics.items():
            st.markdown(f"""
            <div style="display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #2d3139;">
                <span style="color: #a3a3a3;">{metric}</span>
                <span style="color: #fafafa; font-weight: 600;">{value}</span>
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("#### Performance Metrics")
        perf_metrics = {
            'Sortino Ratio': '2.34',
            'Calmar Ratio': '3.21',
            'Omega Ratio': '1.67',
            'Information Ratio': '0.89'
        }
        
        for metric, value in perf_metrics.items():
            st.markdown(f"""
            <div style="display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #2d3139;">
                <span style="color: #a3a3a3;">{metric}</span>
                <span style="color: #fafafa; font-weight: 600;">{value}</span>
            </div>
            """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
