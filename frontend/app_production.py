"""
Streamlit UI メインアプリケーション - 本番環境版

GMOコイン自動売買システムのWebインターフェース（実データ表示）
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
from streamlit.web.server.server import Server
from dotenv import load_dotenv

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from backend.gmo_client import GMOCoinClient
from backend.config_manager import get_config_manager
from backend.logger import get_logger
from backend.strategy import get_strategy_manager
from backend.backtester import Backtester
from backend.risk_manager import RiskManager
from backend.data_fetcher import GMOCoinDataFetcher

# ロガー設定
logger = get_logger()

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
    
    /* エラーメッセージ */
    .error-message {
        background-color: rgba(255, 71, 87, 0.1);
        border: 1px solid #ff4757;
        padding: 1rem;
        border-radius: 5px;
        color: #ff4757;
        margin: 1rem 0;
    }
    
    /* 成功メッセージ */
    .success-message {
        background-color: rgba(0, 212, 170, 0.1);
        border: 1px solid #00d4aa;
        padding: 1rem;
        border-radius: 5px;
        color: #00d4aa;
        margin: 1rem 0;
    }
    
    /* ローディングアニメーション */
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.7; }
        100% { opacity: 1; }
    }
    
    .loading {
        animation: pulse 2s infinite;
    }
    
    /* データフレーム */
    .dataframe {
        background-color: #1a1d24;
        color: #fafafa;
    }
    
    /* タブ */
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
    
    .stTabs [aria-selected="true"] {
        background-color: #ff6b35;
        color: #fafafa;
    }
    </style>
    """, unsafe_allow_html=True)

# ページ設定
st.set_page_config(
    page_title="Chirp Trading System - Production",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSSを適用
apply_custom_css()

# .envファイルを明示的に読み込む
load_dotenv()

# セッション状態の初期化
if 'gmo_client' not in st.session_state:
    try:
        # 環境変数の確認（デバッグ用）
        api_key = os.getenv('GMO_API_KEY')
        api_secret = os.getenv('GMO_API_SECRET')
        
        if not api_key or not api_secret:
            st.error("⚠️ API設定が不完全です。管理者にお問い合わせください。")
            logger.error(f"環境変数不足 - API_KEY: {'設定済み' if api_key else '未設定'}, API_SECRET: {'設定済み' if api_secret else '未設定'}")
            st.session_state.gmo_client = None
        else:
            st.session_state.gmo_client = GMOCoinClient()
            st.success("✅ GMOクライアントが正常に初期化されました。")
    except Exception as e:
        st.error(f"APIクライアントの初期化に失敗しました: {e}")
        st.session_state.gmo_client = None

if 'last_update' not in st.session_state:
    st.session_state.last_update = None

if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False

if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 30  # 秒


def format_jpy(value: float) -> str:
    """日本円フォーマット"""
    return f"¥{value:,.0f}"


def format_percentage(value: float, decimals: int = 2) -> str:
    """パーセンテージフォーマット"""
    return f"{value:.{decimals}f}%"


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


def fetch_real_data():
    """実際のAPIデータを取得"""
    if not st.session_state.gmo_client:
        return None
    
    try:
        # 残高情報を取得
        balance = st.session_state.gmo_client.get_account_balance()
        
        # ポジション情報を取得
        positions = st.session_state.gmo_client.get_positions()
        
        # 取引履歴を取得
        trades = st.session_state.gmo_client.get_trade_history(count=100)
        
        # パフォーマンス指標を計算
        performance = st.session_state.gmo_client.calculate_performance_metrics(trades)
        
        # ティッカー情報を取得（主要通貨）
        tickers = {}
        for symbol in ['BTC_JPY', 'ETH_JPY', 'XRP_JPY', 'LTC_JPY']:
            ticker = st.session_state.gmo_client.get_ticker(symbol)
            if ticker:
                tickers[symbol] = ticker
        
        st.session_state.last_update = datetime.now()
        
        return {
            'balance': balance,
            'positions': positions,
            'trades': trades,
            'performance': performance,
            'tickers': tickers
        }
    
    except Exception as e:
        logger.error(f"データ取得エラー: {e}")
        return None


def main():
    """メインアプリケーション"""
    # ヘッダー
    col1, col2, col3 = st.columns([2, 4, 2])
    
    with col1:
        st.markdown("# 📊 Chirp")
        st.markdown("*Production Trading System*")
    
    with col2:
        # 自動更新トグル
        st.session_state.auto_refresh = st.checkbox(
            "自動更新",
            value=st.session_state.auto_refresh,
            help=f"{st.session_state.refresh_interval}秒ごとに更新"
        )
    
    with col3:
        if st.session_state.last_update:
            st.markdown(f"最終更新: {st.session_state.last_update.strftime('%H:%M:%S')}")
        
        if st.button("🔄 更新", use_container_width=True):
            st.rerun()
    
    # データ取得
    data = fetch_real_data()
    
    if not data:
        st.markdown("""
        <div class="error-message">
            <h3>⚠️ データ取得エラー</h3>
            <p>APIからデータを取得できませんでした。以下を確認してください：</p>
            <ul>
                <li>.envファイルにAPIキーが正しく設定されているか</li>
                <li>インターネット接続が正常か</li>
                <li>GMOコインのAPIが稼働しているか</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        return
    
    # メインタブ
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 ダッシュボード", "💼 ポジション", "📈 取引履歴", "🔄 バックテスト", "⚙️ 設定"])
    
    with tab1:
        dashboard_page(data)
    
    with tab2:
        positions_page(data)
    
    with tab3:
        trades_page(data)
    
    with tab4:
        backtest_page()
    
    with tab5:
        settings_page()
    
    # 自動更新（非ブロッキング）
    if st.session_state.auto_refresh:
        # タイマー用プレースホルダー
        auto_refresh_placeholder = st.empty()
        
        # 最後の更新時刻をチェック
        current_time = datetime.now()
        
        if 'last_auto_refresh' not in st.session_state:
            st.session_state.last_auto_refresh = current_time
        
        # 指定された間隔が経過したかチェック
        time_since_last = (current_time - st.session_state.last_auto_refresh).total_seconds()
        
        if time_since_last >= st.session_state.refresh_interval:
            st.session_state.last_auto_refresh = current_time
            st.rerun()
        else:
            # 残り時間を表示
            remaining_time = int(st.session_state.refresh_interval - time_since_last)
            auto_refresh_placeholder.info(f"⏱️ 自動更新まで {remaining_time} 秒")
            
            # Streamlitの自動更新を使用（より適切な方法）
            st.markdown(f'''
            <script>
                setTimeout(function() {{
                    window.parent.postMessage({{type: 'streamlit:setComponentValue', key: 'auto_refresh_trigger', value: true}}, '*');
                }}, 1000);
            </script>
            ''', unsafe_allow_html=True)


def dashboard_page(data: Dict[str, Any]):
    """ダッシュボードページ"""
    balance = data.get('balance', {})
    performance = data.get('performance', {})
    tickers = data.get('tickers', {})
    
    # エラーチェック
    if 'error' in balance:
        st.error(f"残高取得エラー: {balance['error']}")
        return
    
    # 上部のメトリクス
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_balance = balance.get('total_jpy', 0)
        st.markdown(create_metric_card(
            "総資産",
            format_jpy(total_balance)
        ), unsafe_allow_html=True)
    
    with col2:
        total_pnl = performance.get('total_pnl', 0)
        pnl_color = "positive" if total_pnl >= 0 else "negative"
        st.markdown(create_metric_card(
            "総損益",
            format_jpy(total_pnl),
            delta_color=pnl_color
        ), unsafe_allow_html=True)
    
    with col3:
        win_rate = performance.get('win_rate', 0)
        st.markdown(create_metric_card(
            "勝率",
            format_percentage(win_rate)
        ), unsafe_allow_html=True)
    
    with col4:
        total_trades = performance.get('total_trades', 0)
        st.markdown(create_metric_card(
            "総取引数",
            str(total_trades)
        ), unsafe_allow_html=True)
    
    # 資産内訳
    st.markdown("### 💰 資産内訳")
    
    assets = balance.get('assets', [])
    if assets:
        # JPY以外の資産がある場合はグラフ表示
        non_jpy_assets = [a for a in assets if a['symbol'] != 'JPY' and a['amount'] > 0]
        
        if non_jpy_assets:
            col1, col2 = st.columns([2, 3])
            
            with col1:
                for asset in assets:
                    if asset['amount'] > 0:
                        st.markdown(f"""
                        <div style="display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #2d3139;">
                            <span style="color: #a3a3a3;">{asset['symbol']}</span>
                            <span style="color: #fafafa; font-weight: 600;">{asset['amount']:.8f}</span>
                        </div>
                        """, unsafe_allow_html=True)
            
            with col2:
                # 円グラフ
                fig = go.Figure(data=[go.Pie(
                    labels=[a['symbol'] for a in non_jpy_assets],
                    values=[a['amount'] for a in non_jpy_assets],
                    hole=0.3
                )])
                
                fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor='rgba(26, 29, 36, 1)',
                    plot_bgcolor='rgba(26, 29, 36, 1)',
                    height=300,
                    showlegend=True
                )
                
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("現在、暗号資産のポジションはありません")
    
    # マーケット情報
    st.markdown("### 🌐 マーケット情報")
    
    if tickers:
        cols = st.columns(len(tickers))
        
        for col, (symbol, ticker) in zip(cols, tickers.items()):
            with col:
                last_price = ticker.get('last', 0)
                high = ticker.get('high', 0)
                low = ticker.get('low', 0)
                
                # 24時間変動率の計算（簡易版）
                if high > 0 and low > 0:
                    mid = (high + low) / 2
                    change_pct = ((last_price - mid) / mid) * 100
                    change_color = "positive" if change_pct >= 0 else "negative"
                    change_str = f"{'+' if change_pct >= 0 else ''}{change_pct:.2f}%"
                else:
                    change_str = "N/A"
                    change_color = "normal"
                
                st.markdown(f"""
                <div class="metric-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div class="metric-label">{symbol}</div>
                            <div style="font-size: 1.5rem; font-weight: 600;">{format_jpy(last_price)}</div>
                        </div>
                        <div class="{change_color}" style="font-size: 1.2rem;">{change_str}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)


def positions_page(data: Dict[str, Any]):
    """ポジションページ"""
    positions = data.get('positions', [])
    
    st.markdown("### 💼 保有ポジション")
    
    if positions:
        # ポジションをデータフレームに変換
        df_positions = pd.DataFrame(positions)
        
        # 表示用にフォーマット
        df_display = df_positions.copy()
        df_display['price'] = df_display['price'].apply(format_jpy)
        df_display['lossGain'] = df_display['lossGain'].apply(lambda x: format_jpy(x) if x != 0 else '-')
        df_display['timestamp'] = pd.to_datetime(df_display['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # カラム名を日本語に
        df_display.columns = ['通貨ペア', '売買', '数量', '約定価格', '評価損益', '約定日時']
        
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True
        )
        
        # 評価損益の合計
        total_loss_gain = sum(pos['lossGain'] for pos in positions)
        color = "positive" if total_loss_gain >= 0 else "negative"
        
        st.markdown(f"""
        <div class="metric-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div class="metric-label">評価損益合計</div>
                <div class="metric-value {color}">{format_jpy(total_loss_gain)}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("現在、保有しているポジションはありません")


def trades_page(data: Dict[str, Any]):
    """取引履歴ページ"""
    trades = data.get('trades', [])
    
    st.markdown("### 📈 取引履歴")
    
    if trades:
        # 取引履歴をデータフレームに変換
        df_trades = pd.DataFrame(trades)
        
        # 表示用にフォーマット
        df_display = df_trades.copy()
        df_display['price'] = df_display['price'].apply(format_jpy)
        df_display['fee'] = df_display['fee'].apply(format_jpy)
        df_display['timestamp'] = pd.to_datetime(df_display['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # カラム名を日本語に
        df_display = df_display[['timestamp', 'symbol', 'side', 'size', 'price', 'fee', 'orderId']]
        df_display.columns = ['約定日時', '通貨ペア', '売買', '数量', '約定価格', '手数料', '注文ID']
        
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True
        )
        
        # 統計情報
        st.markdown("### 📊 取引統計")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_fee = sum(trade['fee'] for trade in trades)
            st.markdown(create_metric_card(
                "総手数料",
                format_jpy(total_fee)
            ), unsafe_allow_html=True)
        
        with col2:
            buy_count = len([t for t in trades if t['side'] == 'BUY'])
            sell_count = len([t for t in trades if t['side'] == 'SELL'])
            st.markdown(create_metric_card(
                "買い/売り",
                f"{buy_count} / {sell_count}"
            ), unsafe_allow_html=True)
        
        with col3:
            if trades:
                avg_size = sum(trade['size'] for trade in trades) / len(trades)
                st.markdown(create_metric_card(
                    "平均取引量",
                    f"{avg_size:.8f}"
                ), unsafe_allow_html=True)
    else:
        st.info("取引履歴がありません")


def backtest_page():
    """バックテストページ"""
    st.markdown("### 🔄 バックテスト")
    
    # 注意事項
    st.info("⚠️ バックテスト機能は開発中です。現在はシミュレーションデータで動作します。")
    
    # 設定カラム
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # 戦略選択
        strategy_options = {
            'simple_ma_cross': '単純移動平均クロス',
            'macd_rsi': 'MACD + RSI戦略',
            'bollinger_breakout': 'ボリンジャーバンドブレイクアウト',
            'grid_trading': 'グリッドトレーディング',
            'multi_timeframe': 'マルチタイムフレーム'
        }
        
        selected_strategy = st.selectbox(
            "戦略",
            options=list(strategy_options.keys()),
            format_func=lambda x: strategy_options[x]
        )
    
    with col2:
        # 通貨ペア選択
        symbol = st.selectbox(
            "通貨ペア",
            options=['BTC_JPY', 'ETH_JPY', 'XRP_JPY', 'LTC_JPY'],
            index=0
        )
    
    with col3:
        # 時間枠選択
        timeframe = st.selectbox(
            "時間枠",
            options=['1hour', '4hour', '1day'],
            index=0
        )
    
    # 期間設定
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input(
            "開始日",
            value=datetime.now() - timedelta(days=90),
            max_value=datetime.now() - timedelta(days=1)
        )
    
    with col2:
        end_date = st.date_input(
            "終了日",
            value=datetime.now(),
            min_value=start_date,
            max_value=datetime.now()
        )
    
    # 詳細設定
    with st.expander("詳細設定"):
        col1, col2 = st.columns(2)
        
        with col1:
            initial_capital = st.number_input(
                "初期資金 (円)",
                min_value=100000,
                value=1000000,
                step=100000
            )
            
            position_size = st.slider(
                "ポジションサイズ (%)",
                min_value=1,
                max_value=100,
                value=10
            )
        
        with col2:
            commission = st.number_input(
                "手数料 (%)",
                min_value=0.0,
                max_value=1.0,
                value=0.09,
                step=0.01
            )
            
            slippage = st.number_input(
                "スリッページ (%)",
                min_value=0.0,
                max_value=1.0,
                value=0.01,
                step=0.01
            )
    
    # 実行ボタン
    if st.button("🚀 バックテスト実行", type="primary", use_container_width=True):
        run_backtest_simulation(
            strategy=selected_strategy,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            position_size=position_size/100,
            commission=commission/100,
            slippage=slippage/100
        )


def run_backtest_simulation(strategy, symbol, timeframe, start_date, end_date, 
                            initial_capital, position_size, commission, slippage):
    """バックテストのシミュレーション実行"""
    
    with st.spinner("バックテストを実行中..."):
        # プログレスバー
        progress_bar = st.progress(0)
        
        # シミュレーション結果を生成
        progress_bar.progress(50)
        
        # ランダムな結果を生成
        np.random.seed(42)  # 結果を一定にする
        total_return = np.random.uniform(10, 30)
        sharpe_ratio = np.random.uniform(1.0, 2.0)
        max_drawdown = np.random.uniform(-15, -5)
        win_rate = np.random.uniform(55, 70)
        total_trades = np.random.randint(100, 200)
        profit_factor = np.random.uniform(1.2, 1.8)
        
        progress_bar.progress(100)
        progress_bar.empty()
        
        # 結果表示
        display_backtest_results(
            {
                'total_return': total_return,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'win_rate': win_rate,
                'total_trades': total_trades,
                'profit_factor': profit_factor
            },
            start_date,
            end_date,
            initial_capital
        )


def display_backtest_results(results, start_date, end_date, initial_capital):
    """バックテスト結果を表示"""
    
    st.markdown("### 📊 バックテスト結果")
    
    # サマリーメトリクス
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_return = results['total_return']
        color = "positive" if total_return >= 0 else "negative"
        st.markdown(create_metric_card(
            "総収益率",
            f"{total_return:.2f}%",
            delta_color=color
        ), unsafe_allow_html=True)
    
    with col2:
        sharpe_ratio = results['sharpe_ratio']
        st.markdown(create_metric_card(
            "シャープレシオ",
            f"{sharpe_ratio:.2f}"
        ), unsafe_allow_html=True)
    
    with col3:
        max_dd = results['max_drawdown']
        st.markdown(create_metric_card(
            "最大ドローダウン",
            f"{max_dd:.2f}%",
            delta_color="negative"
        ), unsafe_allow_html=True)
    
    with col4:
        win_rate = results['win_rate']
        st.markdown(create_metric_card(
            "勝率",
            f"{win_rate:.1f}%"
        ), unsafe_allow_html=True)
    
    # 資産曲線
    st.markdown("### 📈 資産曲線")
    
    # シミュレーション用の日付範囲
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    
    # 資産曲線を生成（ランダムウォーク）
    returns = np.random.normal(0.001, 0.02, len(dates))
    returns[0] = 0
    equity_curve = initial_capital * (1 + np.cumsum(returns))
    
    # Buy & Hold曲線
    trend = np.linspace(0, results['total_return'] / 100 * 0.7, len(dates))
    buy_hold = initial_capital * (1 + trend)
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=dates,
        y=equity_curve,
        mode='lines',
        name='戦略',
        line=dict(color='#00d4aa', width=2)
    ))
    
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
        xaxis_title="日付",
        yaxis_title="資産価値 (円)",
        yaxis_tickformat=',.0f',
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 詳細統計
    st.markdown("### 📊 詳細統計")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 取引統計")
        stats = {
            '総取引数': results['total_trades'],
            '勝ちトレード': int(results['total_trades'] * results['win_rate'] / 100),
            '負けトレード': int(results['total_trades'] * (100 - results['win_rate']) / 100),
            'プロフィットファクター': f"{results['profit_factor']:.2f}",
            '平均保有期間': f"{np.random.randint(12, 48)}時間"
        }
        
        for key, value in stats.items():
            st.markdown(f"""
            <div style="display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #2d3139;">
                <span style="color: #a3a3a3;">{key}</span>
                <span style="color: #fafafa; font-weight: 600;">{value}</span>
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("#### リスク指標")
        
        # 期間を日数で計算
        days = (end_date - start_date).days
        annual_factor = 365 / days if days > 0 else 1
        
        risk_metrics = {
            '年率リターン': f"{results['total_return'] * annual_factor:.2f}%",
            '年率ボラティリティ': f"{np.random.uniform(15, 30):.2f}%",
            '最大連続負け': np.random.randint(3, 8),
            'リスクリワード比': f"{np.random.uniform(1.5, 2.5):.2f}",
            'カルマーレシオ': f"{abs(results['total_return'] / results['max_drawdown']):.2f}"
        }
        
        for key, value in risk_metrics.items():
            st.markdown(f"""
            <div style="display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #2d3139;">
                <span style="color: #a3a3a3;">{key}</span>
                <span style="color: #fafafa; font-weight: 600;">{value}</span>
            </div>
            """, unsafe_allow_html=True)


def settings_page():
    """設定ページ"""
    st.markdown("### ⚙️ システム設定")
    
    # 更新間隔設定
    st.markdown("#### 🔄 自動更新設定")
    
    new_interval = st.slider(
        "更新間隔（秒）",
        min_value=10,
        max_value=300,
        value=st.session_state.refresh_interval,
        step=10
    )
    
    if new_interval != st.session_state.refresh_interval:
        st.session_state.refresh_interval = new_interval
        st.success(f"更新間隔を{new_interval}秒に変更しました")
    
    # API接続状態
    st.markdown("#### 🔌 API接続状態")
    
    if st.session_state.gmo_client:
        st.markdown("""
        <div class="success-message">
            <h4>✅ API接続: 正常</h4>
            <p>GMOコインAPIに正常に接続されています</p>
        </div>
        """, unsafe_allow_html=True)
        
        # 環境情報
        env = os.getenv('ENV', 'unknown')
        debug = os.getenv('DEBUG', 'False')
        
        st.markdown(f"""
        <div class="metric-card">
            <h4>環境情報</h4>
            <div style="display: flex; justify-content: space-between; padding: 0.5rem 0;">
                <span>環境:</span>
                <span><strong>{env}</strong></span>
            </div>
            <div style="display: flex; justify-content: space-between; padding: 0.5rem 0;">
                <span>デバッグモード:</span>
                <span><strong>{debug}</strong></span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="error-message">
            <h4>❌ API接続: エラー</h4>
            <p>GMOコインAPIに接続できません</p>
        </div>
        """, unsafe_allow_html=True)
    
    # データ管理
    st.markdown("#### 🗃️ データ管理")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🗑️ キャッシュクリア", use_container_width=True):
            st.cache_data.clear()
            st.success("キャッシュをクリアしました")
    
    with col2:
        if st.button("♻️ セッションリセット", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


if __name__ == "__main__":
    main()
