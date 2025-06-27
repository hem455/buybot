"""
Streamlit UI メインアプリケーション - 本番環境版（リファクタリング版）

GMOコイン自動売買システムのWebインターフェース（実データ表示）
"""

import streamlit as st
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pandas_ta")
import pandas as pd
from streamlit_autorefresh import st_autorefresh
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

# GMOCoinClientはキャッシュ関数内でimport
from backend.config_manager import get_config_manager
from backend.logger import get_logger
from backend.strategy import get_strategy_manager
from backend.backtester import Backtester
from backend.risk_manager import RiskManager
from backend.data_fetcher import GMOCoinDataFetcher
from backend.utils.trade_log_reader import get_trade_log_reader
from backend.utils.alert_system import get_alert_system

# ロガー設定
logger = get_logger()

# カスタムCSSでダークテーマを適用
def apply_custom_css():
    st.markdown("""
    <style>
    /* Font Awesome CDN */
    @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css');
    
    /* === カラーパレット === */
    :root{
        --bg:      #0b0b0d;
        --panel:   #151619;
        --border:  #2c2d31;
        --text:    #e8e8e8;
        --subtext: #969696;
        --accent1: #ff6b35;
        --accent2: #ff5e14;
        --success: #19c37d;
        --danger:  #ff5050;
        --warning: #ffa726;
    }
    
    html,body,.stApp{
        background:var(--bg);
        color:var(--text);
        line-height:1.4;
    }

    /* === サイドバー === */
    section[data-testid="stSidebar"]{
        background:var(--panel);
        border-right:1px solid var(--border);
    }
    
    /* サイドバーアイテム */
    .sidebar-item{
        display:flex;
        align-items:center;
        gap:.6rem;
        padding:.5rem 1rem;
        color:var(--subtext);
        cursor:pointer;
        border-radius:6px;
        transition:.25s;
    }
    .sidebar-item.active{
        background:linear-gradient(90deg,var(--accent1),var(--accent2));
        color:#fff;
    }
    .sidebar-item:hover{
        background:rgba(255,107,53,.1);
        color:var(--accent1);
    }

    /* === メトリックカード === */
    .metric-card{
        background:var(--panel);
        border:1px solid var(--border);
        border-radius:10px;
        padding:1.25rem 1.5rem;
        box-shadow:0 2px 4px rgba(0,0,0,.4);
        display:flex;
        flex-direction:column;
        gap:.3rem;
        margin-bottom:1rem;
        transition:.25s;
    }
    .metric-card:hover{
        border-color:var(--accent1);
        box-shadow:0 4px 8px rgba(255,107,53,.2);
    }
    
    .metric-label{
        font-size:.8rem;
        color:var(--subtext);
        letter-spacing:.05em;
        text-transform:uppercase;
        display:flex;
        align-items:center;
        gap:.5rem;
    }
    .metric-value{
        font-size:1.6rem;
        font-weight:600;
        color:var(--text);
    }
    .positive{color:var(--success);} 
    .negative{color:var(--danger);}
    .warning{color:var(--warning);}

    /* === ボタン === */
    .stButton>button{
        background:linear-gradient(135deg,var(--accent1),var(--accent2));
        border:none;
        border-radius:6px;
        padding:.6rem 1.2rem;
        color:#fff;
        font-weight:600;
        transition:.25s;
    }
    .stButton>button:hover{
        transform:translateY(-2px);
        box-shadow:0 6px 16px rgba(255,91,39,.35);
    }

    /* === 危険なボタン（パニック機能用） === */
    .panic-button{
        background:linear-gradient(135deg,#ff4757,#ff3742) !important;
        border:none !important;
        border-radius:6px !important;
        padding:.6rem 1.2rem !important;
        color:#fff !important;
        font-weight:600 !important;
        transition:.25s !important;
    }
    .panic-button:hover{
        transform:translateY(-2px) !important;
        box-shadow:0 6px 16px rgba(255,71,87,.4) !important;
    }

    /* === DataFrame === */
    .stDataFrame{
        background:var(--panel);
        border:1px solid var(--border);
        border-radius:8px;
    }
    .stDataFrame table{
        background:var(--panel);
        color:var(--text);
    }
    .stDataFrame th{
        background:var(--border);
        color:var(--text);
        font-weight:600;
    }

    /* === タブ === */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
        background-color: var(--panel);
        padding: 0.5rem;
        border-radius: 10px;
        border: 1px solid var(--border);
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        border-radius: 5px;
        color: var(--subtext);
        font-weight: 500;
        transition: .25s;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg,var(--accent1),var(--accent2));
        color: #fff;
    }

    /* === エラー/成功メッセージ === */
    .error-message {
        background: rgba(255, 80, 80, 0.1);
        border: 1px solid #ff5050;
        padding: 1rem;
        border-radius: 8px;
        color: #ff5050;
        margin: 1rem 0;
    }
    
    .success-message {
        background: rgba(25, 195, 125, 0.1);
        border: 1px solid #19c37d;
        padding: 1rem;
        border-radius: 8px;
        color: #19c37d;
        margin: 1rem 0;
    }

    /* === レスポンシブ調整 === */
    @media (max-width: 768px) {
        .metric-card {
            padding: 1rem;
        }
        .metric-value {
            font-size: 1.4rem;
        }
    }

    /* === チャートエリア === */
    .plotly-graph-div {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 8px;
    }

    /* === ローディングアニメーション === */
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.7; }
        100% { opacity: 1; }
    }
    
    .loading {
        animation: pulse 2s infinite;
    }

    /* === コンテナ余白 === */
    .main-container {
        padding: 0 1rem;
        max-width: 1400px;
        margin: 0 auto;
    }

    /* === インプットフィールド === */
    .stSelectbox > div > div {
        background: var(--panel);
        border: 1px solid var(--border);
        color: var(--text);
    }
    
    .stNumberInput > div > div > input {
        background: var(--panel);
        border: 1px solid var(--border);
        color: var(--text);
    }

    .stTextInput > div > div > input {
        background: var(--panel);
        border: 1px solid var(--border);
        color: var(--text);
    }
    </style>
    """, unsafe_allow_html=True)

# ページ設定
st.set_page_config(
    page_title="Chirp Trading System - Production",
    page_icon="📈",
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
            # フラグとして設定（実際のクライアントはキャッシュ関数内で作成）
            st.session_state.gmo_client = True
            st.success("✅ GMOクライアントが正常に初期化されました。")
    except Exception as e:
        st.error(f"APIクライアントの初期化に失敗しました: {e}")
        logger.error(f"GMOクライアント初期化エラー: {e}")
        st.session_state.gmo_client = None

if 'last_update' not in st.session_state:
    st.session_state.last_update = None

if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False

if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 30  # 秒


# === ユーティリティ関数 ===
def format_jpy(value: float) -> str:
    """日本円フォーマット"""
    return f"¥{value:,.0f}"

def format_percentage(value: float, decimals: int = 2) -> str:
    """パーセンテージフォーマット"""
    return f"{value:.{decimals}f}%"

def get_status_color(value: float, threshold_good: float = 0, threshold_warning: float = None) -> str:
    """値に基づいてステータス色を取得"""
    if threshold_warning and value < threshold_warning:
        return "negative"
    elif value >= threshold_good:
        return "positive"
    else:
        return "warning"


# === 共通UIコンポーネント ===
def create_metric_card(label: str, value: str, delta: str = None, delta_color: str = "normal", icon: str = ""):
    """メトリクスカードを作成（強化版）"""
    delta_html = ""
    if delta:
        delta_class = "positive" if delta_color == "positive" else "negative" if delta_color == "negative" else ""
        delta_html = f'<div class="{delta_class}">{delta}</div>'
    
    icon_html = f'<i class="{icon}"></i>' if icon else ""
    
    return f"""
    <div class="metric-card">
        <div class="metric-label">{icon_html}{label}</div>
        <div class="metric-value">{value}</div>
        {delta_html}
    </div>
    """

def create_strategy_toggle(strategy_name: str, strategy_key: str, description: str = ""):
    """戦略ON/OFFトグルを生成"""
    enabled = st.toggle(
        strategy_name,
        value=st.session_state.strategy_states.get(strategy_key, False),
        key=f"{strategy_key}_toggle",
        help=description
    )
    st.session_state.strategy_states[strategy_key] = enabled
    
    if enabled:
        st.success("🟢 稼働中")
    else:
        st.info("⚪ 停止中")
    
    return enabled

def create_section_header(title: str, icon: str = "", description: str = ""):
    """セクションヘッダーを作成"""
    icon_html = f'<i class="fas fa-{icon}"></i>' if icon else ''
    desc_html = f'<p style="color: var(--subtext); margin: 0.5rem 0 0 0; font-size: 1rem;">{description}</p>' if description else ''
    
    st.markdown(f"""
    <div style='text-align: center; padding: 2rem 0; border-bottom: 1px solid var(--border); margin-bottom: 2rem;'>
        <h1 style='color: var(--accent1); margin: 0; font-size: 2.2rem;'>
            {icon_html} {title}
        </h1>
        {desc_html}
    </div>
    """, unsafe_allow_html=True)

def show_error_message(message: str):
    """エラーメッセージを表示"""
    st.error(f"⚠️ {message}")

def show_success_message(message: str):
    """成功メッセージを表示"""
    st.success(f"✅ {message}")

def show_warning_message(message: str):
    """警告メッセージを表示"""
    st.warning(f"⚠️ {message}")

@st.cache_data(ttl=10, persist=False)  # 10秒間キャッシュ、メモリのみ使用
def fetch_cached_data(api_key_hash: str):
    """キャッシュ化されたAPIデータ取得"""
    from backend.gmo_client import GMOCoinClient
    
    try:
        # GMOClientは環境変数から自動でAPIキーを読み込む
        gmo_client = GMOCoinClient()
    except ValueError as e:
        from backend.logger import get_logger
        logger = get_logger()
        logger.error(f"GMOクライアント初期化エラー: {e}")
        return None
    
    try:
        # 残高情報を取得
        balance = gmo_client.get_account_balance()
        
        # ポジション情報を取得（証拠金取引 + 現物保有）
        positions = gmo_client.get_all_positions()
        
        # 取引履歴を取得
        trades = gmo_client.get_latest_executions(count=100)
        
        # パフォーマンス指標を計算
        performance = gmo_client.calculate_performance_metrics(trades)
        
        # ティッカー情報を取得（主要通貨）
        tickers = {}
        for symbol in ['BTC_JPY', 'ETH_JPY', 'XRP_JPY', 'LTC_JPY']:
            ticker = gmo_client.get_ticker(symbol)
            if ticker:
                tickers[symbol] = ticker
        
        # 当日取引回数を取得
        today_trade_count = gmo_client.get_today_trade_count()
        
        # APIレート状況を取得
        api_rate_status = gmo_client.get_api_rate_status()
        
        # 残高履歴を取得
        balance_history = gmo_client.get_balance_history(30)
        
        # 資産履歴を取得（新機能）
        asset_history = gmo_client.get_asset_history_data(30)
        
        # 新機能: 有効注文とロスカット価格
        active_orders = gmo_client.get_active_orders()
        liquidation_info = gmo_client.calculate_liquidation_price()
        
        # リスクメトリクス取得
        risk_metrics = gmo_client.get_risk_metrics_for_ui()
        
        return {
            'balance': balance,
            'positions': positions,
            'trades': trades,
            'performance': performance,
            'tickers': tickers,
            'today_trade_count': today_trade_count,
            'api_rate_status': api_rate_status,
            'balance_history': balance_history,
            'asset_history': asset_history,
            'active_orders': active_orders,
            'liquidation_info': liquidation_info,
            'risk_metrics': risk_metrics
        }
    
    except Exception as e:
        from backend.logger import get_logger
        logger = get_logger()
        logger.error(f"データ取得エラー: {e}")
        return None


def fetch_real_data():
    """実際のAPIデータを取得（キャッシュ機能付き）"""
    try:
        # APIキーのハッシュを作成（キャッシュキーとして使用）
        import hashlib
        import os
        api_key = os.getenv('GMO_API_KEY', '')
        
        if not api_key:
            st.error("⚠️ APIキーが設定されていません。.envファイルを確認してください。")
            return None
        
        api_key_hash = hashlib.md5(api_key.encode()).hexdigest()[:8]
        
        # キャッシュされたデータを取得
        data = fetch_cached_data(api_key_hash)
        
        # 最終更新時刻を設定
        if data:
            st.session_state.last_update = datetime.now()
        
        return data
        
    except Exception as e:
        from backend.logger import get_logger
        logger = get_logger()
        logger.error(f"データ取得エラー: {e}")
        st.error(f"⚠️ データ取得エラー: {e}")
        return None


def main():
    """メインアプリケーション"""
    apply_custom_css()
    
    # サイドバーでページ選択
    with st.sidebar:
        st.markdown("""
        <div style='text-align: center; padding: 1.5rem 0; border-bottom: 1px solid var(--border); margin-bottom: 1rem;'>
            <h2 style='color: var(--accent1); margin: 0; font-size: 1.4rem;'>
                <i class='fas fa-chart-line'></i> GMOコイン自動売買
            </h2>
            <p style='color: var(--subtext); margin: 0.5rem 0 0 0; font-size: 0.8rem;'>Production System</p>
        </div>
        """, unsafe_allow_html=True)
        
        page = st.radio(
            "ページ選択",
            ["📊 ダッシュボード", "💼 ポジション & オーダー", "⚙️ 戦略コントロール", "📋 ログ & アラート", "🛡️ リスク管理", "🔙 バックテスト", "⚙️ 設定"],
            index=0
        )

    # データ取得
    try:
        data = fetch_real_data()
    except (ConnectionError, TimeoutError) as e:
        st.error(f"ネットワークエラー: 接続に失敗しました - {str(e)}")
        st.stop()
    except ValueError as e:
        st.error(f"設定エラー: APIキーやパラメータを確認してください - {str(e)}")
        st.stop()
    except KeyError as e:
        st.error(f"データ形式エラー: 予期しないレスポンス形式です - {str(e)}")
        st.stop()
    except Exception as e:
        st.error(f"予期しないエラーが発生しました: {str(e)}")
        st.error("システム管理者にお問い合わせください。")
        st.stop()

    # ページルーティング
    if page == "📊 ダッシュボード":
        dashboard_page(data)
    elif page == "💼 ポジション & オーダー":
        positions_page(data)
    elif page == "⚙️ 戦略コントロール":
        strategies_control_page(data)
    elif page == "📋 ログ & アラート":
        logs_alerts_page(data)
    elif page == "🛡️ リスク管理":
        risk_management_page(data)
    elif page == "🔙 バックテスト":
        backtest_page()
    elif page == "⚙️ 設定":
        settings_page()


def dashboard_page(data: Dict[str, Any]):
    """ダッシュボードページ"""
    # データがNoneの場合の処理
    if data is None:
        st.error("⚠️ データを取得できませんでした。ネットワーク接続を確認してください。")
        st.info("💡 APIキーの設定やネットワーク接続を確認してください。")
        return
    
    balance = data.get('balance', {})
    performance = data.get('performance', {})
    tickers = data.get('tickers', {})
    
    # 残高データもNoneの場合を処理
    if balance is None:
        st.error("⚠️ 残高データを取得できませんでした。")
        return
    
    # エラーチェック
    if 'error' in balance:
        st.error(f"残高取得エラー: {balance['error']}")
        return
    
    # 上部のメトリクス
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # 真の総資産計算：JPY残高 + 保有コインの評価額
        jpy_balance = balance.get('total_jpy', 0)
        positions = data.get('positions', [])
        tickers = data.get('tickers', {})
        
        # 現物保有の評価額を加算（ティッカーから現在価格を取得）
        spot_value = 0
        assets = balance.get('assets', [])
        for asset in assets:
            if asset['symbol'] != 'JPY' and asset['amount'] > 0:
                # 対応するティッカーから現在価格を取得
                symbol_ticker = f"{asset['symbol']}_JPY"
                if symbol_ticker in tickers:
                    current_price = tickers[symbol_ticker].get('last', 0)
                    spot_value += current_price * asset['amount']
        
        # 証拠金取引の評価損益を加算（証拠金は既にJPY残高に含まれているため、評価損益のみ）
        margin_pnl = 0
        margin_positions = [p for p in positions if p.get('type') != 'SPOT']
        for pos in margin_positions:
            margin_pnl += pos.get('lossGain', 0)
        
        # 真の総資産 = JPY残高 + 現物保有評価額 + 証拠金取引評価損益
        total_assets = jpy_balance + spot_value + margin_pnl
        
        # デバッグ情報（開発環境のみ表示）
        debug_info = None
        if os.getenv('DEBUG', '').lower() in ['true', '1', 'yes']:
            debug_info = f"JPY: {format_jpy(jpy_balance)} + 現物: {format_jpy(spot_value)} + 証拠金損益: {format_jpy(margin_pnl)}"
        
        st.markdown(create_metric_card(
            "総資産",
            format_jpy(total_assets),
            delta=debug_info,
            delta_color="positive" if total_assets > jpy_balance else "normal",
            icon="fas fa-wallet"
        ), unsafe_allow_html=True)
    
    with col2:
        # 含み損益を計算（現物保有の評価損益）
        positions = data.get('positions', [])
        unrealized_pnl = 0
        
        # 現物保有の含み損益を計算
        spot_holdings = [p for p in positions if p.get('type') == 'SPOT']
        for holding in spot_holdings:
            current_price = holding.get('price', 0)
            size = holding.get('size', 0)
            # 簡易的に購入価格を現在価格の95%と仮定（実際は取得価格が必要）
            estimated_purchase_price = current_price * 0.95
            unrealized_pnl += (current_price - estimated_purchase_price) * size
        
        pnl_color = "positive" if unrealized_pnl >= 0 else "negative"
        st.markdown(create_metric_card(
            "含み損益",
            format_jpy(unrealized_pnl),
            delta_color=pnl_color,
            icon="fas fa-chart-line"
        ), unsafe_allow_html=True)
    
    with col3:
        win_rate = performance.get('win_rate', 0)
        st.markdown(create_metric_card(
            "勝率",
            format_percentage(win_rate),
            icon="fas fa-bullseye"
        ), unsafe_allow_html=True)
    
    with col4:
        # 当日確定損益（セッション状態で管理）
        if 'daily_realized_pnl' not in st.session_state:
            st.session_state.daily_realized_pnl = 0
        
        daily_pnl_color = "positive" if st.session_state.daily_realized_pnl >= 0 else "negative"
        st.markdown(create_metric_card(
            "当日確定損益",
            format_jpy(st.session_state.daily_realized_pnl),
            delta_color=daily_pnl_color,
            icon="fas fa-calendar-day"
        ), unsafe_allow_html=True)
    
    # 資産内訳（JPY換算）
    st.markdown("""
    <h3 style="display: flex; align-items: center; gap: 0.5rem;">
        <i class="fas fa-wallet" style="color: var(--accent1);"></i>
        資産内訳（JPY換算）
    </h3>
    """, unsafe_allow_html=True)
    
    assets = balance.get('assets', [])
    tickers = data.get('tickers', {})
    
    if assets:
        # JPY換算での資産内訳を計算
        asset_values = []
        
        # JPY残高を追加
        if jpy_balance > 0:
            asset_values.append({
                'symbol': 'JPY',
                'amount': jpy_balance,
                'jpy_value': jpy_balance
            })
        
        # 各暗号資産のJPY換算値を計算
        for asset in assets:
            if asset['symbol'] != 'JPY' and asset['amount'] > 0:
                symbol_ticker = f"{asset['symbol']}_JPY"
                if symbol_ticker in tickers:
                    current_price = tickers[symbol_ticker].get('last', 0)
                    jpy_value = current_price * asset['amount']
                    if jpy_value > 0:
                        asset_values.append({
                            'symbol': asset['symbol'],
                            'amount': asset['amount'],
                            'jpy_value': jpy_value
                        })
        
        # 証拠金取引の評価損益を追加（プラスの場合のみ）
        if margin_pnl > 0:
            asset_values.append({
                'symbol': '証拠金損益',
                'amount': margin_pnl,
                'jpy_value': margin_pnl
            })
        
        if len(asset_values) > 1:  # JPYのみでない場合
            col1, col2 = st.columns([2, 3])
            
            with col1:
                for asset_data in asset_values:
                    symbol = asset_data['symbol']
                    jpy_value = asset_data['jpy_value']
                    percentage = (jpy_value / total_assets * 100) if total_assets > 0 else 0
                    
                    if symbol == 'JPY':
                        display_amount = format_jpy(jpy_value)
                    elif symbol == '証拠金損益':
                        display_amount = format_jpy(jpy_value)
                    else:
                        display_amount = f"{asset_data['amount']:.6f} ({format_jpy(jpy_value)})"
                    
                    st.markdown(f"""
                    <div style="display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #2d3139;">
                        <span style="color: #a3a3a3;">{symbol}</span>
                        <div style="text-align: right;">
                            <div style="color: #fafafa; font-weight: 600;">{display_amount}</div>
                            <div style="color: #969696; font-size: 0.9rem;">{percentage:.1f}%</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            
            with col2:
                # 円グラフ（JPY換算値で表示）
                fig = go.Figure(data=[go.Pie(
                    labels=[a['symbol'] for a in asset_values],
                    values=[a['jpy_value'] for a in asset_values],
                    hole=0.4,
                    marker=dict(
                        colors=['#FF6B35', '#FF5E14', '#E8511A', '#D4441F', '#C03724'],
                        line=dict(color='#151619', width=2)
                    ),
                    textfont=dict(color='#e8e8e8', size=12),
                    textinfo='label+percent',
                    texttemplate='%{label}<br>%{percent}'
                )])
                
                fig.update_layout(
                    paper_bgcolor='#151619',
                    plot_bgcolor='#151619',
                    font=dict(color='#e8e8e8'),
                    height=280,
                    showlegend=True,
                    legend=dict(
                        font=dict(color='#969696'),
                        orientation='v',
                        x=1.1
                    ),
                    margin=dict(l=10, r=80, t=10, b=10)
                )
                
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("現在、JPY以外の資産保有はありません")
    
    # マーケット情報
    st.markdown("""
    <h3 style="display: flex; align-items: center; gap: 0.5rem;">
        <i class="fas fa-globe" style="color: var(--accent1);"></i>
        マーケット情報
    </h3>
    """, unsafe_allow_html=True)
    
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
                    if change_pct >= 0:
                        change_color = "#FF6B35"  # オレンジで統一
                        change_str = f"+{change_pct:.2f}%"
                    else:
                        change_color = "#969696"  # グレーでマイナス表示
                        change_str = f"{change_pct:.2f}%"
                else:
                    change_str = "N/A"
                    change_color = "#969696"
                
                st.markdown(f"""
                <div class="metric-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div class="metric-label">{symbol}</div>
                            <div style="font-size: 1.5rem; font-weight: 600;">{format_jpy(last_price)}</div>
                        </div>
                        <div style="color: {change_color}; font-size: 1.2rem; font-weight: 600;">{change_str}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    
    # === 新機能エリア ===
    st.markdown("---")  # セパレーター
    
    # 稼働戦略のON/OFFスイッチ
    st.markdown("""
    <h3 style="display: flex; align-items: center; gap: 0.5rem;">
        <i class="fas fa-cogs" style="color: var(--accent1);"></i>
        稼働戦略管理
    </h3>
    """, unsafe_allow_html=True)
    
    # セッション状態で戦略の状態を管理
    if 'strategy_states' not in st.session_state:
        st.session_state.strategy_states = {
            'ma_cross': False,
            'macd_rsi': False,
            'grid_trading': False,
            'ml_based': False
        }
    
    strategy_col1, strategy_col2 = st.columns(2)
    
    with strategy_col1:
        st.markdown("#### 📈 トレンド戦略")
        
        # MA Cross Strategy（コンポーネント化）
        create_strategy_toggle(
            "MA Cross Strategy", 
            "ma_cross", 
            "移動平均線のクロスオーバーで売買判断"
        )
        
        # MACD-RSI Strategy（コンポーネント化）
        create_strategy_toggle(
            "MACD-RSI Strategy", 
            "macd_rsi", 
            "MACD とRSI を組み合わせた戦略"
        )
    
    with strategy_col2:
        st.markdown("#### 🎯 その他戦略")
        
        # Grid Trading Strategy（コンポーネント化）
        create_strategy_toggle(
            "Grid Trading Strategy", 
            "grid_trading", 
            "価格幅でグリッド状に売買を配置"
        )
        
        # ML Based Strategy（コンポーネント化）
        create_strategy_toggle(
            "ML Based Strategy", 
            "ml_based", 
            "機械学習モデルによる予測売買"
        )
    
    # APIレート制限メーター
    st.markdown("### 🚦 システム状態")
    
    api_col1, api_col2 = st.columns(2)
    
    with api_col1:
        # APIレート上限メーター（Plotly Gaugeで視覚的インパクトUP）
        api_status = data.get('api_rate_status', {})
        current_calls = api_status.get('current_calls', 0)
        max_calls = api_status.get('max_calls', 20)
        usage_percentage = api_status.get('usage_percentage', 0)
        status = api_status.get('status', 'unknown')
        
        # ステータスに応じて色を決定
        if status == 'normal':
            gauge_color = "green"
            status_emoji = "🟢"
        elif status == 'warning':
            gauge_color = "yellow"
            status_emoji = "🟡"
        elif status == 'critical':
            gauge_color = "red"
            status_emoji = "🔴"
        else:
            gauge_color = "gray"
            status_emoji = "⚪"
        
        # オレンジテーマAPIゲージ
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=usage_percentage,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': f"API使用率", 'font': {'color': '#e8e8e8', 'size': 16}},
            number={'font': {'color': '#FF6B35', 'size': 24}},
            gauge={
                'axis': {'range': [None, 100], 'tickcolor': '#969696'},
                'bar': {'color': '#FF6B35', 'thickness': 0.8},
                'steps': [
                    {'range': [0, 50], 'color': "rgba(255, 107, 53, 0.1)"},
                    {'range': [50, 80], 'color': "rgba(255, 107, 53, 0.2)"},
                    {'range': [80, 100], 'color': "rgba(255, 107, 53, 0.3)"}
                ],
                'threshold': {
                    'line': {'color': "#FF5E14", 'width': 3},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))
        
        fig_gauge.update_layout(
            paper_bgcolor='#151619',
            plot_bgcolor='#151619',
            font={'color': "#e8e8e8"},
            height=180,
            margin=dict(l=10, r=10, t=30, b=10)
        )
        
        st.plotly_chart(fig_gauge, use_container_width=True)
        
        # 詳細情報
        st.markdown(f"""
        <div style="text-align: center; color: #a3a3a3; font-size: 0.9rem;">
            {current_calls}/{max_calls} req/s
        </div>
        """, unsafe_allow_html=True)
    
    with api_col2:
        # 当日の取引回数（実データ）
        today_trades = data.get('today_trade_count', 0)
        
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">本日取引回数</div>
            <div style="font-size: 1.2rem; font-weight: 600;">{today_trades} 回</div>
        </div>
        """, unsafe_allow_html=True)
        
        # リセットボタン
        if st.button("📊 統計リセット", use_container_width=True):
            # セッション状態のリセット（実データには影響しない）
            if 'daily_realized_pnl' in st.session_state:
                st.session_state.daily_realized_pnl = 0
            st.success("📊 統計をリセットしました")
            st.rerun()
    
    # 総資産推移チャート（過去30日）
    st.markdown("""
    <h3 style="display: flex; align-items: center; gap: 0.5rem;">
        <i class="fas fa-chart-area" style="color: var(--accent1);"></i>
        総資産推移（過去30日）
    </h3>
    """, unsafe_allow_html=True)
    
    balance_history = data.get('balance_history', [])
    
    # 総資産推移グラフ（データベース履歴 vs 従来の履歴）
    asset_history = data.get('asset_history', [])
    
    if asset_history and len(asset_history) > 1:
        # 新機能: データベースから取得した正確な総資産履歴
        dates = [datetime.fromisoformat(entry['date']) for entry in asset_history]
        total_assets_history = [entry['total_assets'] for entry in asset_history]
        jpy_balance_history = [entry['jpy_balance'] for entry in asset_history]
        spot_value_history = [entry['spot_value'] for entry in asset_history]
        
        # グラフ作成（詳細な内訳付き）
        fig = go.Figure()
        
        # 総資産推移ライン（メインライン）
        fig.add_trace(go.Scatter(
            x=dates,
            y=total_assets_history,
            mode='lines+markers',
            name='総資産',
            line=dict(color='#FF6B35', width=4),
            marker=dict(size=8, color='#FF5E14', line=dict(color='#FF6B35', width=2)),
            fill='tozeroy',
            fillcolor='rgba(255, 107, 53, 0.1)',
            hovertemplate='<b>総資産</b><br>¥%{y:,.0f}<br>%{x|%Y/%m/%d}<extra></extra>'
        ))
        
        # JPY残高ライン（サブライン）
        fig.add_trace(go.Scatter(
            x=dates,
            y=jpy_balance_history,
            mode='lines',
            name='JPY残高',
            line=dict(color='#969696', width=2, dash='dot'),
            hovertemplate='<b>JPY残高</b><br>¥%{y:,.0f}<br>%{x|%Y/%m/%d}<extra></extra>'
        ))
        
        # 現物評価額ライン（サブライン）
        if any(v > 0 for v in spot_value_history):
            fig.add_trace(go.Scatter(
                x=dates,
                y=spot_value_history,
                mode='lines',
                name='現物評価額',
                line=dict(color='#4ECDC4', width=2, dash='dash'),
                hovertemplate='<b>現物評価額</b><br>¥%{y:,.0f}<br>%{x|%Y/%m/%d}<extra></extra>'
            ))
    
    elif balance_history and len(balance_history) > 1:
        # フォールバック: 従来の簡易履歴
        dates = [datetime.fromisoformat(entry['date']) for entry in balance_history]
        
        # 実際の総資産履歴を計算（実データベース）
        total_assets_history = []
        
        for entry in balance_history:
            jpy_balance_hist = entry['balance']
            # 実際の総資産計算（現在と同じロジック）
            # 注意: 過去の現物評価額・証拠金損益は取得できないため、現在値を基準に推定
            total_estimated = jpy_balance_hist + spot_value + margin_pnl
            total_assets_history.append(total_estimated)
        
        # グラフ作成（総資産のみ）
        fig = go.Figure()
        
        # 総資産推移ライン（オレンジグラデーション）
        fig.add_trace(go.Scatter(
            x=dates,
            y=total_assets_history,
            mode='lines+markers',
            name='総資産（推定）',
            line=dict(color='#FF6B35', width=4),
            marker=dict(size=6, color='#FF5E14', line=dict(color='#FF6B35', width=2)),
            fill='tozeroy',
            fillcolor='rgba(255, 107, 53, 0.2)',
            hovertemplate='<b>総資産（推定）</b><br>¥%{y:,.0f}<br>%{x|%Y/%m/%d}<extra></extra>'
        ))
        
        # オレンジテーマレイアウト
        fig.update_layout(
            paper_bgcolor='#151619',
            plot_bgcolor='#151619',
            font_color='#e8e8e8',
            height=320,
            showlegend=False,  # 単一ラインなので凡例不要
            xaxis=dict(
                showgrid=True, 
                gridcolor='rgba(255, 107, 53, 0.1)',
                color='#969696',
                title="",
                tickformat='%m/%d'
            ),
            yaxis=dict(
                showgrid=True, 
                gridcolor='rgba(255, 107, 53, 0.1)',
                color='#969696',
                title="",
                tickformat="¥,.0f"
            ),
            margin=dict(l=10, r=10, t=10, b=10),
            hovermode='closest'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        # データが不足している場合
        st.info("📊 総資産履歴データが不足しています。データを蓄積して美しい推移グラフを表示しましょう！")
        
        # 手動データ保存ボタン
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("💾 今日の総資産を保存", use_container_width=True):
                try:
                    from backend.gmo_client import GMOCoinClient
                    gmo_client = GMOCoinClient()
                    
                    if gmo_client.save_daily_assets("手動保存"):
                        st.success("✅ 総資産データを保存しました！")
                        st.balloons()
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("❌ 保存に失敗しました - データベース書き込みエラーの可能性があります")
                        st.info("💡 **トラブルシューティング**: ログファイルを確認してください")
                except ImportError as e:
                    logger.error(f"GMOClient インポートエラー: {e}")
                    st.error("❌ システムモジュールの読み込みに失敗しました")
                    st.info("💡 **解決方法**: アプリケーションを再起動してください")
                except ConnectionError as e:
                    logger.error(f"API接続エラー: {e}")
                    st.error("❌ GMOコインAPIへの接続に失敗しました")
                    st.info("💡 **確認事項**: インターネット接続とAPI設定を確認してください")
                except PermissionError as e:
                    logger.error(f"ファイルアクセス権限エラー: {e}")
                    st.error("❌ データベースファイルへの書き込み権限がありません")
                    st.info("💡 **解決方法**: アプリケーションを管理者権限で実行してください")
                except Exception as e:
                    logger.error(f"資産保存の予期しないエラー: {e}", exc_info=True)
                    st.error(f"❌ 予期しないエラーが発生しました: {type(e).__name__}")
                    st.info("💡 **サポート**: このエラーが継続する場合は、ログファイルと共にお問い合わせください")
        
        with col2:
            # 期間選択ボタン（今後の機能拡張用）
            period = st.selectbox("表示期間", ["30日", "90日", "1年"], key="asset_history_period")
        
        with col3:
            st.info("💡 毎日データを蓄積すると美しい総資産推移グラフが表示されます。")
        
        logger.info("総資産推移グラフ: 履歴データ不足のため表示スキップ")
    
    # 総資産サマリー（オレンジテーマ）
    st.markdown(f"""
    <div class="metric-card" style="text-align: center; background: linear-gradient(135deg, rgba(255, 107, 53, 0.1), rgba(255, 94, 20, 0.05)); border: 1px solid rgba(255, 107, 53, 0.3);">
        <div style="color: #FF6B35; font-size: 1.8rem; font-weight: 700; margin-bottom: 0.5rem;">
            {format_jpy(total_assets)}
        </div>
        <div style="color: #969696; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.1em;">
            現在の総資産
        </div>
    </div>
    """, unsafe_allow_html=True)


def positions_page(data: Dict[str, Any]):
    """ポジション&注文ページ"""
    # データがNoneの場合の処理
    if data is None:
        st.error("⚠️ データを取得できませんでした。ネットワーク接続を確認してください。")
        st.info("💡 APIキーの設定やネットワーク接続を確認してください。")
        return
    
    positions = data.get('positions', [])
    active_orders = data.get('active_orders', [])
    liquidation_info = data.get('liquidation_info', {})
    tickers = data.get('tickers', {})
    
    # === 1. 保有ポジション ===
    st.markdown("""
    <h3 style="display: flex; align-items: center; gap: 0.5rem;">
        <i class="fas fa-briefcase" style="color: var(--accent1);"></i>
        保有ポジション
    </h3>
    """, unsafe_allow_html=True)
    
    if positions:
        # 証拠金取引と現物保有を分類
        # GMOコインAPI: get_positions() = 証拠金取引, get_spot_holdings() = 現物保有
        margin_positions = [p for p in positions if p.get('type') != 'SPOT']
        spot_holdings = [p for p in positions if p.get('type') == 'SPOT']
        
        # 念のため、typeが設定されていないポジションは証拠金取引として扱う
        untyped_positions = [p for p in positions if 'type' not in p]
        if untyped_positions:
            margin_positions.extend(untyped_positions)
        
        # 証拠金取引ポジション（拡張版）
        if margin_positions:
            st.markdown("#### 📊 証拠金取引ポジション")
            
            # ポジション詳細データフレーム作成
            position_data = []
            for pos in margin_positions:
                symbol = pos.get('symbol', '')
                current_price = tickers.get(symbol, {}).get('last', 0)
                liquidation_price = liquidation_info.get(symbol, {}).get('liquidation_price', 0)
                margin_rate = liquidation_info.get(symbol, {}).get('current_margin_rate', 0)
                
                # リアルタイム評価損益計算
                entry_price = pos.get('price', 0)
                size = pos.get('size', 0)
                side = pos.get('side', '')
                
                if current_price > 0 and entry_price > 0:
                    if side == 'BUY':
                        unrealized_pnl = (current_price - entry_price) * size
                    else:
                        unrealized_pnl = (entry_price - current_price) * size
                else:
                    unrealized_pnl = pos.get('lossGain', 0)
                
                position_data.append({
                    'symbol': symbol,
                    'side': side,
                    'size': size,
                    'entry_price': format_jpy(entry_price),
                    'current_price': format_jpy(current_price) if current_price > 0 else '取得中...',
                    'unrealized_pnl': unrealized_pnl,
                    'liquidation_price': format_jpy(liquidation_price) if liquidation_price > 0 else '計算中...',
                    'margin_rate': f"{margin_rate:.1f}%" if margin_rate > 0 else '計算中...',
                    'timestamp': pd.to_datetime(pos.get('timestamp')).strftime('%Y-%m-%d %H:%M:%S') if pos.get('timestamp') else 'N/A'
                })
            
            if position_data:
                df_positions = pd.DataFrame(position_data)
                
                # 表示用フォーマット
                df_display = df_positions.copy()
                df_display['unrealized_pnl_display'] = df_display['unrealized_pnl'].apply(
                    lambda x: f"{'🟢' if x >= 0 else '🔴'} {format_jpy(x)}"
                )
                
                # アクションボタン列追加
                df_display['action'] = '🔹 詳細'
                
                # 列名設定
                df_display = df_display[['symbol', 'side', 'size', 'entry_price', 'current_price', 
                                       'unrealized_pnl_display', 'liquidation_price', 'margin_rate', 'action']]
                df_display.columns = ['通貨ペア', '売買', '数量', '約定価格', '現在価格', 
                                    'リアルタイム評価損益', 'ロスカット価格', '証拠金維持率', 'アクション']
                
                st.dataframe(df_display, use_container_width=True, hide_index=True)
                
                # ポジション操作パネル
                with st.expander("🔧 ポジション操作", expanded=False):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("🚨 全ポジション一括決済", type="secondary", use_container_width=True):
                            st.warning("⚠️ 実装中: 全ポジション決済機能")
                    
                    with col2:
                        selected_symbol = st.selectbox(
                            "個別決済",
                            options=[p['symbol'] for p in position_data],
                            key="position_close_select"
                        )
                        if st.button(f"決済: {selected_symbol}", use_container_width=True):
                            st.warning(f"⚠️ 実装中: {selected_symbol} 決済機能")
        
        # 現物保有（拡張版）
        if spot_holdings:
            st.markdown("#### 💰 現物保有")
            spot_data = []
            
            for holding in spot_holdings:
                symbol = holding.get('symbol', '')
                size = holding.get('size', 0)
                current_price = holding.get('price', 0)
                
                # 評価額計算
                current_value = size * current_price if current_price > 0 else 0
                
                spot_data.append({
                    'symbol': symbol,
                    'size': size,
                    'current_price': format_jpy(current_price) if current_price > 0 else '価格取得中...',
                    'current_value': format_jpy(current_value),
                    'action': '🔹 詳細'
                })
            
            if spot_data:
                df_spot = pd.DataFrame(spot_data)
                df_spot.columns = ['通貨ペア', '保有量', '現在価格', '評価額', 'アクション']
                st.dataframe(df_spot, use_container_width=True, hide_index=True)
        
        # サマリー統計
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if margin_positions:
                total_unrealized = sum(
                    pos['unrealized_pnl'] for pos in position_data if 'unrealized_pnl' in pos
                )
                color = "positive" if total_unrealized >= 0 else "negative"
                st.markdown(create_metric_card(
                    "証拠金取引 評価損益",
                    format_jpy(total_unrealized),
                    delta_color=color,
                    icon="fas fa-chart-line"
                ), unsafe_allow_html=True)
        
        with col2:
            if spot_holdings:
                total_spot_value = sum(s['size'] * s['price'] for s in spot_holdings if s['price'] > 0)
                st.markdown(create_metric_card(
                    "現物保有 総評価額",
                    format_jpy(total_spot_value),
                    icon="fas fa-coins"
                ), unsafe_allow_html=True)
        
        with col3:
            total_positions = len(margin_positions) + len(spot_holdings)
            st.markdown(create_metric_card(
                "総ポジション数",
                f"{total_positions}件",
                icon="fas fa-list-alt"
            ), unsafe_allow_html=True)
    
    else:
        st.info("現在、保有しているポジションがありません。")
    
    # === 2. 有効注文一覧 ===
    st.markdown("""
    <h3 style="display: flex; align-items: center; gap: 0.5rem;">
        <i class="fas fa-list-ul" style="color: var(--accent1);"></i>
        有効注文
    </h3>
    """, unsafe_allow_html=True)
    
    if active_orders:
        order_data = []
        for order in active_orders:
            order_data.append({
                'orderId': order.get('orderId', ''),
                'symbol': order.get('symbol', ''),
                'side': order.get('side', ''),
                'orderType': order.get('orderType', ''),
                'size': order.get('size', 0),
                'price': format_jpy(order.get('price', 0)),
                'status': order.get('status', ''),
                'timestamp': pd.to_datetime(order.get('timestamp')).strftime('%Y-%m-%d %H:%M:%S') if order.get('timestamp') else ''
            })
        
        if order_data:
            df_orders = pd.DataFrame(order_data)
            df_orders.columns = ['注文ID', '通貨ペア', '売買', '注文種別', '数量', '価格', 'ステータス', '注文日時']
            st.dataframe(df_orders, use_container_width=True, hide_index=True)
            
            # 注文操作
            with st.expander("🔧 注文操作", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    selected_order = st.selectbox(
                        "キャンセルする注文",
                        options=df_orders['注文ID'].tolist(),
                        key="order_cancel_select"
                    )
                    if st.button("❌ 注文キャンセル", use_container_width=True):
                        st.warning(f"⚠️ 実装中: 注文 {selected_order} キャンセル機能")
                
                with col2:
                    if st.button("🚨 全注文一括キャンセル", type="secondary", use_container_width=True):
                        st.warning("⚠️ 実装中: 全注文キャンセル機能")
    else:
        st.info("現在、有効な注文がありません。")
    
    # === 3. 手動取引パネル ===
    st.markdown("""
    <h3 style="display: flex; align-items: center; gap: 0.5rem;">
        <i class="fas fa-hand-point-right" style="color: var(--accent1);"></i>
        手動取引
    </h3>
    """, unsafe_allow_html=True)
    
    with st.expander("📈 クイック注文", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🟢 買い注文")
            symbol_buy = st.selectbox("通貨ペア", ['BTC_JPY', 'ETH_JPY', 'XRP_JPY', 'LTC_JPY'], key="buy_symbol")
            order_type_buy = st.radio("注文種別", ['成行', '指値'], key="buy_type")
            size_buy = st.number_input("数量", min_value=0.0001, step=0.0001, format="%.4f", key="buy_size")
            
            if order_type_buy == '指値':
                price_buy = st.number_input("価格", min_value=1.0, step=1.0, key="buy_price")
            
            if st.button("🟢 買い注文実行", type="primary", use_container_width=True):
                st.warning("⚠️ 実装中: 買い注文機能")
        
        with col2:
            st.markdown("#### 🔴 売り注文")
            symbol_sell = st.selectbox("通貨ペア", ['BTC_JPY', 'ETH_JPY', 'XRP_JPY', 'LTC_JPY'], key="sell_symbol")
            order_type_sell = st.radio("注文種別", ['成行', '指値'], key="sell_type")
            size_sell = st.number_input("数量", min_value=0.0001, step=0.0001, format="%.4f", key="sell_size")
            
            if order_type_sell == '指値':
                price_sell = st.number_input("価格", min_value=1.0, step=1.0, key="sell_price")
            
            if st.button("🔴 売り注文実行", type="secondary", use_container_width=True):
                st.warning("⚠️ 実装中: 売り注文機能")
    
    # === 4. パニック機能 ===
    st.markdown("""
    <h3 style="display: flex; align-items: center; gap: 0.5rem;">
        <i class="fas fa-exclamation-triangle" style="color: #ff4757;"></i>
        緊急操作
    </h3>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # セキュアなStreamlitネイティブボタンで置き換え
        if st.button("🚫 PANIC: 全注文取消", key="panic_cancel_orders", use_container_width=True, type="secondary"):
            st.warning("⚠️ 実装中: パニック機能 - 全注文取消")
            st.info("この機能は開発中です。実装完了時に実際の注文取消が実行されます。")
    
    with col2:
        if st.button("❌ PANIC: 全ポジション決済", key="panic_close_positions", use_container_width=True, type="secondary"):
            st.warning("⚠️ 実装中: パニック機能 - 全ポジション決済")
            st.info("この機能は開発中です。実装完了時に実際のポジション決済が実行されます。")


def trades_page(data: Dict[str, Any]):
    """取引履歴ページ"""
    # データがNoneの場合の処理
    if data is None:
        st.error("⚠️ データを取得できませんでした。ネットワーク接続を確認してください。")
        st.info("💡 APIキーの設定やネットワーク接続を確認してください。")
        return
    
    trades = data.get('trades', [])
    performance = data.get('performance', {})
    tickers = data.get('tickers', {})
    
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
        st.info("""
        📋 **取引履歴が表示されていません**
        
        💡 **考えられる理由**:
        - **現物購入のみ**: 現物での暗号資産購入は約定履歴APIに含まれません
        - **レバレッジ取引未実施**: `/v1/latestExecutions`はレバレッジ取引の約定のみ対象
        - **API制限**: GMOコインAPIは現物取引とレバレッジ取引のみ対応
        
        🔧 **確認方法**:
        1. **現物保有確認**: 上記「現物保有」セクションで暗号資産を確認
        2. **レバレッジ取引**: 証拠金取引で実際の売買を行うと履歴が表示されます
        3. **GMOコイン会員ページ**: 詳細な取引履歴は会員ページで確認可能
        
        ℹ️ **現在の動作**: APIは正常に動作しており、取得件数0は正常なレスポンスです
        """)


def backtest_page():
    """⑥⑦バックテスト設定層・結果層"""
    create_section_header("🔄 バックテスト", "📊", "戦略の過去データでの検証と最適化")
    
    # セッション状態の初期化
    if 'backtest_result' not in st.session_state:
        st.session_state.backtest_result = None
    if 'backtest_running' not in st.session_state:
        st.session_state.backtest_running = False
    
    # タブ構成
    tab1, tab2 = st.tabs(["⚙️ バックテスト設定", "📊 結果表示"])
    
    with tab1:
        backtest_settings_section()
    
    with tab2:
        backtest_results_section()





def backtest_results_section():
    """⑦バックテスト結果層"""
    st.markdown("#### 📊 バックテスト結果")
    
    if st.session_state.backtest_result is None:
        st.info("👈 左の「バックテスト設定」タブでバックテストを実行してください。")
        
        # サンプル結果表示ボタン
        if st.button("🎭 デモ結果を表示", help="サンプルのバックテスト結果を表示します"):
            st.session_state.backtest_result = generate_demo_backtest_result(
                'ma_cross_strategy', 'BTC_JPY', 
                datetime.now() - timedelta(days=30), 
                datetime.now() - timedelta(days=1), 
                1000000
            )
            st.rerun()
        return
    
    result = st.session_state.backtest_result
    summary = result.get('summary', {})
    
    # === サマリーメトリクス ===
    st.markdown("**📈 パフォーマンスサマリー**")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_return_pct = summary.get('total_return_pct', 0)
        color = "normal" if total_return_pct >= 0 else "inverse"
        delta_color = "positive" if total_return_pct >= 0 else "negative"
        
        st.markdown(create_metric_card(
            "💰 総収益率",
            f"{total_return_pct:.2f}%",
            delta=f"{'+' if total_return_pct >= 0 else ''}{total_return_pct:.2f}%",
            delta_color=delta_color,
            icon="📈" if total_return_pct >= 0 else "📉"
        ), unsafe_allow_html=True)
    
    with col2:
        final_balance = summary.get('final_balance', 0)
        initial_capital = summary.get('initial_capital', 1000000)
        profit = final_balance - initial_capital
        
        st.markdown(create_metric_card(
            "💵 最終資産",
            format_jpy(final_balance),
            delta=f"{'+' if profit >= 0 else ''}{format_jpy(profit)}",
            delta_color="positive" if profit >= 0 else "negative",
            icon="💎"
        ), unsafe_allow_html=True)
    
    with col3:
        sharpe_ratio = summary.get('sharpe_ratio', 0)
        sharpe_color = "positive" if sharpe_ratio > 1.0 else "warning" if sharpe_ratio > 0.5 else "negative"
        
        st.markdown(create_metric_card(
            "📊 シャープレシオ",
            f"{sharpe_ratio:.2f}",
            delta="優秀" if sharpe_ratio > 1.0 else "良好" if sharpe_ratio > 0.5 else "要改善",
            delta_color=sharpe_color,
            icon="⭐"
        ), unsafe_allow_html=True)
    
    with col4:
        max_dd = summary.get('max_drawdown_pct', 0)
        dd_color = "positive" if max_dd < 10 else "warning" if max_dd < 20 else "negative"
        
        st.markdown(create_metric_card(
            "📉 最大DD",
            f"{max_dd:.1f}%",
            delta="低リスク" if max_dd < 10 else "中リスク" if max_dd < 20 else "高リスク",
            delta_color=dd_color,
            icon="🛡️"
        ), unsafe_allow_html=True)
    
    st.markdown("---")
    
    # === 詳細メトリクス ===
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🎯 取引統計**")
        
        trade_metrics = {
            '総取引数': f"{summary.get('total_trades', 0)}回",
            '勝率': f"{summary.get('win_rate', 0):.1f}%",
            '勝ちトレード': f"{summary.get('winning_trades', 0)}回",
            '負けトレード': f"{summary.get('losing_trades', 0)}回",
            'プロフィットファクター': f"{summary.get('profit_factor', 0):.2f}",
            '総手数料': format_jpy(summary.get('total_fees', 0))
        }
        
        for key, value in trade_metrics.items():
            st.markdown(f"""
            <div style="display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid var(--border-color);">
                <span style="color: var(--text-color-secondary);">{key}</span>
                <span style="color: var(--text-color); font-weight: 600;">{value}</span>
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("**🆚 Buy & Hold比較**")
        
        buy_hold = result.get('buy_hold_comparison', {})
        strategy_return = summary.get('total_return_pct', 0)
        buy_hold_return = buy_hold.get('total_return_pct', 0)
        outperforms = strategy_return > buy_hold_return
        
        comparison_metrics = {
            '戦略リターン': f"{strategy_return:.2f}%",
            'Buy & Holdリターン': f"{buy_hold_return:.2f}%",
            'アウトパフォーム': f"{'+' if outperforms else ''}{strategy_return - buy_hold_return:.2f}%",
            '戦略シャープレシオ': f"{summary.get('sharpe_ratio', 0):.2f}",
            'Buy & Holdシャープレシオ': f"{buy_hold.get('sharpe_ratio', 0):.2f}",
            '判定': "🎉 戦略の勝利!" if outperforms else "😞 Buy & Holdの勝利"
        }
        
        for key, value in comparison_metrics.items():
            color = "var(--success-color)" if key == "判定" and outperforms else "var(--error-color)" if key == "判定" else "var(--text-color)"
            st.markdown(f"""
            <div style="display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid var(--border-color);">
                <span style="color: var(--text-color-secondary);">{key}</span>
                <span style="color: {color}; font-weight: 600;">{value}</span>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # === 資産曲線グラフ ===
    display_backtest_charts(result)
    
    # === 詳細データ表示 ===
    with st.expander("📋 詳細データ"):
        st.json(result, expanded=False)


def display_backtest_charts(result: dict):
    """バックテスト結果のチャートを表示"""
    st.markdown("**📈 資産推移チャート**")
    
    equity_curve = result.get('equity_curve', {})
    timestamps = equity_curve.get('timestamps', [])
    equity_values = equity_curve.get('equity', [])
    
    if not timestamps or not equity_values:
        st.warning("📊 資産曲線データがありません")
        return
    
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        
        # 日付を変換
        dates = pd.to_datetime(timestamps)
        
        # Buy & Hold曲線を計算
        buy_hold_comparison = result.get('buy_hold_comparison', {})
        buy_hold_return = buy_hold_comparison.get('total_return_pct', 0)
        initial_value = equity_values[0] if equity_values else 1000000
        
        # Buy & Hold曲線（単純な線形増加として近似）
        buy_hold_values = [initial_value * (1 + (buy_hold_return / 100) * i / len(equity_values)) 
                          for i in range(len(equity_values))]
        
        # グラフ作成
        fig = go.Figure()
        
        # 戦略の資産曲線
        fig.add_trace(go.Scatter(
            x=dates,
            y=equity_values,
            mode='lines',
            name='戦略',
            line=dict(color='#00d4aa', width=3),
            hovertemplate='<b>戦略</b><br>日付: %{x}<br>資産: ¥%{y:,.0f}<extra></extra>'
        ))
        
        # Buy & Hold曲線
        fig.add_trace(go.Scatter(
            x=dates,
            y=buy_hold_values,
            mode='lines',
            name='Buy & Hold',
            line=dict(color='#ff6b6b', width=2, dash='dash'),
            hovertemplate='<b>Buy & Hold</b><br>日付: %{x}<br>資産: ¥%{y:,.0f}<extra></extra>'
        ))
        
        # レイアウト設定
        fig.update_layout(
            title="資産推移比較",
            xaxis_title="日付",
            yaxis_title="資産額 (円)",
            template="plotly_dark",
            hovermode="x unified",
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01
            ),
            height=500
        )
        
        # Y軸フォーマット
        fig.update_yaxis(tickformat=",.0f")
        
        st.plotly_chart(fig, use_container_width=True)
        
        # ドローダウンチャート
        st.markdown("**📉 ドローダウン分析**")
        
        # ドローダウン計算
        peak = pd.Series(equity_values).expanding().max()
        drawdown = (pd.Series(equity_values) - peak) / peak * 100
        
        fig_dd = go.Figure()
        
        fig_dd.add_trace(go.Scatter(
            x=dates,
            y=drawdown,
            mode='lines',
            fill='tonegative',
            name='ドローダウン',
            line=dict(color='#ff6b6b', width=2),
            fillcolor='rgba(255, 107, 107, 0.3)',
            hovertemplate='<b>ドローダウン</b><br>日付: %{x}<br>DD: %{y:.1f}%<extra></extra>'
        ))
        
        fig_dd.update_layout(
            title="ドローダウン推移",
            xaxis_title="日付",
            yaxis_title="ドローダウン (%)",
            template="plotly_dark",
            height=300
        )
        
        st.plotly_chart(fig_dd, use_container_width=True)
        
    except ImportError:
        st.error("📊 Plotlyが利用できません。グラフ表示にはplotlyのインストールが必要です。")
    except Exception as e:
        st.error(f"📊 グラフ表示エラー: {e}")


def display_backtest_results_legacy(results, start_date, end_date, initial_capital):
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


def create_strategy_control_panel(strategy_info: Dict[str, Any]) -> None:
    """戦略コントロールパネルを作成"""
    strategy_id = strategy_info['id']
    strategy_name = strategy_info['name']
    state = strategy_info.get('state', 'stopped')
    performance = strategy_info.get('performance', {})
    parameters = strategy_info.get('parameters', {})
    current_params = strategy_info.get('current_params', parameters)
    
    # 戦略状態に応じた色設定
    state_colors = {
        'active': '#19c37d',
        'paused': '#ff6b35', 
        'stopped': '#969696',
        'error': '#ff5050'
    }
    state_color = state_colors.get(state, '#969696')
    
    # 戦略カードのベース
    st.markdown(f"""
    <div class="metric-card" style="margin-bottom: 1.5rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <div>
                <h4 style="margin: 0; color: var(--text);">{strategy_name}</h4>
                <p style="margin: 0.25rem 0 0 0; color: var(--subtext); font-size: 0.9rem;">{strategy_info.get('description', '')}</p>
            </div>
            <div style="text-align: right;">
                <div style="color: {state_color}; font-size: 0.9rem; font-weight: 600; text-transform: uppercase;">
                    ● {state}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 制御パネル
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        # 開始/停止ボタン
        if state == 'stopped' or state == 'error':
            if st.button(f"🚀 開始", key=f"{strategy_id}_start", use_container_width=True):
                strategy_manager = get_strategy_manager()
                if strategy_manager.start_strategy(strategy_id, current_params):
                    st.success(f"✅ {strategy_name}を開始しました")
                    st.rerun()
                else:
                    st.error(f"❌ {strategy_name}の開始に失敗しました")
        
        elif state == 'active':
            if st.button(f"⏸️ 停止", key=f"{strategy_id}_stop", type="secondary", use_container_width=True):
                strategy_manager = get_strategy_manager()
                if strategy_manager.stop_strategy(strategy_id):
                    st.success(f"✅ {strategy_name}を停止しました")
                    st.rerun()
                else:
                    st.error(f"❌ {strategy_name}の停止に失敗しました")
        
        elif state == 'paused':
            if st.button(f"▶️ 再開", key=f"{strategy_id}_resume", use_container_width=True):
                strategy_manager = get_strategy_manager()
                if strategy_manager.resume_strategy(strategy_id):
                    st.success(f"✅ {strategy_name}を再開しました")
                    st.rerun()
                else:
                    st.error(f"❌ {strategy_name}の再開に失敗しました")
    
    with col2:
        # 一時停止ボタン (アクティブ時のみ)
        if state == 'active':
            if st.button(f"⏸️ 一時停止", key=f"{strategy_id}_pause", use_container_width=True):
                strategy_manager = get_strategy_manager()
                if strategy_manager.pause_strategy(strategy_id):
                    st.success(f"✅ {strategy_name}を一時停止しました")
                    st.rerun()
                else:
                    st.error(f"❌ {strategy_name}の一時停止に失敗しました")
        else:
            st.write("")  # スペース確保
    
    with col3:
        # 設定ボタン
        if st.button("⚙️", key=f"{strategy_id}_settings", help="パラメータ設定", use_container_width=True):
            st.session_state[f"{strategy_id}_show_params"] = not st.session_state.get(f"{strategy_id}_show_params", False)
    
    # パフォーマンス表示
    if performance:
        perf_col1, perf_col2, perf_col3, perf_col4 = st.columns(4)
        
        with perf_col1:
            total_trades = performance.get('total_trades', 0)
            st.metric("総取引数", f"{total_trades}")
        
        with perf_col2:
            win_rate = performance.get('win_rate', 0)
            st.metric("勝率", f"{win_rate:.1%}")
        
        with perf_col3:
            total_pnl = performance.get('total_pnl', 0)
            pnl_color = "normal" if total_pnl >= 0 else "inverse"
            st.metric("総損益", f"{total_pnl:+.0f}円", delta_color=pnl_color)
        
        with perf_col4:
            uptime = performance.get('uptime_hours', 0)
            st.metric("稼働時間", f"{uptime:.1f}h")
    
    # パラメータ設定パネル (トグル表示)
    if st.session_state.get(f"{strategy_id}_show_params", False):
        st.markdown("---")
        st.markdown("#### ⚙️ パラメータ設定")
        
        # パラメータ入力フォーム
        updated_params = {}
        param_changed = False
        
        # パラメータごとに入力ウィジェットを生成
        param_cols = st.columns(min(len(parameters), 3))
        
        for i, (param_name, default_value) in enumerate(parameters.items()):
            col_idx = i % len(param_cols)
            with param_cols[col_idx]:
                current_value = current_params.get(param_name, default_value)
                
                if isinstance(default_value, int):
                    new_value = st.number_input(
                        param_name,
                        value=current_value,
                        step=1,
                        key=f"{strategy_id}_{param_name}_int"
                    )
                elif isinstance(default_value, float):
                    new_value = st.number_input(
                        param_name,
                        value=current_value,
                        step=0.01,
                        format="%.3f",
                        key=f"{strategy_id}_{param_name}_float"
                    )
                elif isinstance(default_value, bool):
                    new_value = st.checkbox(
                        param_name,
                        value=current_value,
                        key=f"{strategy_id}_{param_name}_bool"
                    )
                else:
                    new_value = st.text_input(
                        param_name,
                        value=str(current_value),
                        key=f"{strategy_id}_{param_name}_str"
                    )
                
                updated_params[param_name] = new_value
                if new_value != current_value:
                    param_changed = True
        
        # パラメータ更新ボタン
        if param_changed:
            if st.button(f"💾 パラメータ更新", key=f"{strategy_id}_update_params", type="primary"):
                strategy_manager = get_strategy_manager()
                if strategy_manager.update_strategy_parameters(strategy_id, updated_params):
                    st.success(f"✅ {strategy_name}のパラメータを更新しました")
                    st.rerun()
                else:
                    st.error(f"❌ {strategy_name}のパラメータ更新に失敗しました")


def create_strategy_overview_card(strategies_status: List[Dict[str, Any]]) -> None:
    """戦略全体の概要カードを作成"""
    active_count = sum(1 for s in strategies_status if s.get('state') == 'active')
    total_count = len(strategies_status)
    
    # 全体のパフォーマンス集計
    total_trades = sum(s.get('performance', {}).get('total_trades', 0) for s in strategies_status)
    total_pnl = sum(s.get('performance', {}).get('total_pnl', 0) for s in strategies_status)
    total_errors = sum(s.get('performance', {}).get('error_count', 0) for s in strategies_status)
    
    # 勝率計算
    winning_trades = sum(s.get('performance', {}).get('winning_trades', 0) for s in strategies_status)
    overall_win_rate = winning_trades / total_trades if total_trades > 0 else 0
    
    st.markdown(f"""
    <div class="metric-card" style="background: linear-gradient(135deg, #1a1a1d, #2d2d30); margin-bottom: 2rem;">
        <h3 style="margin: 0 0 1rem 0; color: var(--accent1);">📊 戦略システム概要</h3>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem;">
            <div>
                <div class="metric-label">稼働戦略</div>
                <div class="metric-value" style="color: {'#19c37d' if active_count > 0 else '#969696'};">
                    {active_count} / {total_count}
                </div>
            </div>
            <div>
                <div class="metric-label">総取引数</div>
                <div class="metric-value">{total_trades}</div>
            </div>
            <div>
                <div class="metric-label">全体勝率</div>
                <div class="metric-value">{overall_win_rate:.1%}</div>
            </div>
            <div>
                <div class="metric-label">総損益</div>
                <div class="metric-value {'positive' if total_pnl >= 0 else 'negative'}">
                    {total_pnl:+.0f}円
                </div>
            </div>
            <div>
                <div class="metric-label">エラー数</div>
                <div class="metric-value" style="color: {'#ff5050' if total_errors > 0 else '#969696'};">
                    {total_errors}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def strategies_control_page(data: Dict[str, Any]):
    """戦略コントロールページ"""
    # データがNoneの場合の処理
    if data is None:
        st.error("⚠️ データを取得できませんでした。ネットワーク接続を確認してください。")
        st.info("💡 APIキーの設定やネットワーク接続を確認してください。")
        return
    
    st.markdown("""
    <h1 style="display: flex; align-items: center; gap: 0.5rem; color: var(--text-primary);">
        <i class="fas fa-cogs" style="color: var(--accent1);"></i>
        戦略コントロール
    </h1>
    """, unsafe_allow_html=True)
    
    # StrategyManagerから最新情報を取得
    try:
        strategy_manager = get_strategy_manager()
        strategies_status = strategy_manager.get_all_strategies_status()
        
        # 概要カード
        create_strategy_overview_card(strategies_status)
        
        # 各戦略のコントロールパネル
        st.markdown("### 🎯 個別戦略制御")
        
        for strategy_info in strategies_status:
            create_strategy_control_panel(strategy_info)
        
        # リアルタイムシグナル表示
        st.markdown("---")
        st.markdown("### 📡 最新シグナル")
        
        active_strategies = strategy_manager.get_active_strategies()
        
        if active_strategies:
            signal_data = []
            for strategy_id, strategy in active_strategies.items():
                performance = strategy_manager.get_strategy_performance(strategy_id)
                if performance:
                    last_signal = performance.get('last_signal')
                    last_signal_time = performance.get('last_signal_time')
                    
                    if last_signal and last_signal_time:
                        signal_data.append({
                            '戦略': strategy_id,
                            'シグナル': last_signal,
                            '時刻': last_signal_time[:19] if last_signal_time else 'N/A'  # ISO時刻の短縮
                        })
            
            if signal_data:
                signal_df = pd.DataFrame(signal_data)
                st.dataframe(signal_df, use_container_width=True)
            else:
                st.info("📊 まだシグナルが発生していません")
        else:
            st.info("⚪ 稼働中の戦略がありません")
    
    except Exception as e:
        st.error(f"❌ 戦略情報の取得に失敗しました: {e}")
        logger.error(f"戦略コントロールページでエラー: {e}")


def logs_alerts_page(data: Dict[str, Any]):
    """ログ&アラートページ"""
    # データがNoneの場合の処理
    if data is None:
        st.warning("⚠️ APIデータを取得できませんでしたが、ログとアラート機能は利用可能です。")
    
    st.markdown("""
    <h1 style="display: flex; align-items: center; gap: 0.5rem; color: var(--text-primary);">
        <i class="fas fa-clipboard-list" style="color: var(--accent1);"></i>
        ログ&アラート
    </h1>
    """, unsafe_allow_html=True)
    
    # タブ構成
    tab1, tab2, tab3, tab4 = st.tabs(["📊 取引ログ", "🚨 アラート", "📈 ログ分析", "⚙️ システム状態"])
    
    # 取引ログリーダーとアラートシステムを取得
    log_reader = get_trade_log_reader()
    alert_system = get_alert_system()
    
    with tab1:
        st.markdown("### 📊 取引ログ")
        
        # フィルター設定
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            days_filter = st.selectbox("期間", [1, 3, 7, 14, 30], index=2)
        
        with col2:
            strategy_filter = st.selectbox("戦略", ["全て", "MA Cross", "MACD RSI", "Grid Trading", "手動"])
        
        with col3:
            side_filter = st.selectbox("売買", ["全て", "BUY", "SELL"])
        
        with col4:
            if st.button("🔄 更新"):
                st.rerun()
        
        # 最近の取引ログを取得
        try:
            recent_trades = log_reader.get_recent_trades(limit=100)
            
            if recent_trades:
                # フィルタリング
                filtered_trades = recent_trades
                
                if strategy_filter != "全て":
                    filtered_trades = [t for t in filtered_trades if t['strategy'] == strategy_filter]
                
                if side_filter != "全て":
                    filtered_trades = [t for t in filtered_trades if t['side'] == side_filter]
                
                # 統計情報
                if filtered_trades:
                    total_trades = len(filtered_trades)
                    buy_trades = len([t for t in filtered_trades if t['side'] == 'BUY'])
                    sell_trades = len([t for t in filtered_trades if t['side'] == 'SELL'])
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.markdown(create_metric_card(
                            "総取引数",
                            str(total_trades),
                            icon="fas fa-exchange-alt"
                        ), unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown(create_metric_card(
                            "買い注文",
                            str(buy_trades),
                            icon="fas fa-arrow-up",
                            delta_color="positive"
                        ), unsafe_allow_html=True)
                    
                    with col3:
                        st.markdown(create_metric_card(
                            "売り注文",
                            str(sell_trades),
                            icon="fas fa-arrow-down",
                            delta_color="negative"
                        ), unsafe_allow_html=True)
                    
                    with col4:
                        success_rate = (total_trades / 100 * 100) if total_trades > 0 else 0
                        st.markdown(create_metric_card(
                            "実行成功率",
                            f"{success_rate:.1f}%",
                            icon="fas fa-check-circle"
                        ), unsafe_allow_html=True)
                
                # 取引ログテーブル
                st.markdown("#### 📋 取引履歴")
                
                # DataFrameに変換して表示
                if filtered_trades:
                    df_trades = pd.DataFrame(filtered_trades)
                    
                    # 列の並び替え
                    columns_order = ['timestamp', 'pair', 'side', 'quantity', 'price', 'value', 'fee', 'net_pnl', 'strategy', 'status']
                    df_display = df_trades[columns_order]
                    
                    # 列名を日本語化
                    df_display.columns = ['時刻', '通貨ペア', '売買', '数量', '価格', '取引額', '手数料', '純損益', '戦略', 'ステータス']
                    
                    st.dataframe(
                        df_display,
                        use_container_width=True,
                        height=400
                    )
                else:
                    st.info("フィルター条件に該当する取引がありません")
                
            else:
                st.info("取引ログが見つかりません")
                
        except Exception as e:
            st.error(f"取引ログ取得エラー: {e}")
    
    with tab2:
        st.markdown("### 🚨 リアルタイムアラート")
        
        # アラート制御
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 アラート更新"):
                st.rerun()
        
        with col2:
            if st.button("✅ 全て確認済み"):
                for alert in alert_system.recent_alerts:
                    alert.acknowledged = True
                st.success("全アラートを確認済みにしました")
                st.rerun()
        
        with col3:
            if st.button("🗑️ 履歴クリア"):
                alert_system.clear_alerts()
                st.success("アラート履歴をクリアしました")
                st.rerun()
        
        # アラート統計
        alert_stats = alert_system.get_alert_statistics(days=7)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(create_metric_card(
                "総アラート数",
                str(alert_stats['total_alerts']),
                icon="fas fa-bell"
            ), unsafe_allow_html=True)
        
        with col2:
            error_count = alert_stats['by_level'].get('error', 0) + alert_stats['by_level'].get('critical', 0)
            st.markdown(create_metric_card(
                "エラー・警告",
                str(error_count),
                icon="fas fa-exclamation-triangle",
                delta_color="negative" if error_count > 0 else "positive"
            ), unsafe_allow_html=True)
        
        with col3:
            acknowledged_count = alert_stats['acknowledged_count']
            st.markdown(create_metric_card(
                "確認済み",
                str(acknowledged_count),
                icon="fas fa-check"
            ), unsafe_allow_html=True)
        
        with col4:
            pending_count = alert_stats['total_alerts'] - acknowledged_count
            st.markdown(create_metric_card(
                "未確認",
                str(pending_count),
                icon="fas fa-clock",
                delta_color="warning" if pending_count > 0 else "positive"
            ), unsafe_allow_html=True)
        
        # 最近のアラート一覧
        recent_alerts = alert_system.get_recent_alerts(limit=50)
        
        if recent_alerts:
            st.markdown("#### 🚨 最近のアラート")
            
            for alert in recent_alerts:
                # アラートレベルに応じた色設定
                level_colors = {
                    'info': '#17a2b8',
                    'warning': '#ffc107', 
                    'error': '#dc3545',
                    'critical': '#721c24'
                }
                
                level_icons = {
                    'info': 'fas fa-info-circle',
                    'warning': 'fas fa-exclamation-triangle',
                    'error': 'fas fa-times-circle',
                    'critical': 'fas fa-radiation'
                }
                
                color = level_colors.get(alert['level'], '#17a2b8')
                icon = level_icons.get(alert['level'], 'fas fa-bell')
                
                # アラートカード
                acknowledged_badge = "✅" if alert['acknowledged'] else "🔴"
                
                st.markdown(f"""
                <div style="
                    background: var(--panel);
                    border: 1px solid {color};
                    border-radius: 8px;
                    padding: 1rem;
                    margin: 0.5rem 0;
                    border-left: 4px solid {color};
                ">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div style="flex: 1;">
                            <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
                                <i class="{icon}" style="color: {color};"></i>
                                <strong style="color: {color};">{alert['level'].upper()}</strong>
                                <span style="color: var(--subtext);">•</span>
                                <span style="color: var(--subtext);">{alert['timestamp']}</span>
                                <span style="color: var(--subtext);">•</span>
                                <span style="color: var(--subtext);">{alert['strategy']}</span>
                                <span style="margin-left: auto;">{acknowledged_badge}</span>
                            </div>
                            <h4 style="margin: 0 0 0.5rem 0; color: var(--text);">{alert['title']}</h4>
                            <p style="margin: 0; color: var(--subtext);">{alert['message']}</p>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # 確認ボタン
                if not alert['acknowledged']:
                    if st.button(f"確認済み", key=f"ack_{alert['id']}"):
                        alert_system.acknowledge_alert(alert['id'])
                        st.rerun()
        else:
            st.info("アラートはありません")
    
    with tab3:
        st.markdown("### 📈 ログ分析")
        
        # 日次サマリー
        daily_summary = log_reader.get_daily_summary(days=30)
        
        if daily_summary:
            # 日次パフォーマンスチャート
            fig = go.Figure()
            
            dates = [s['date'] for s in daily_summary]
            total_pnl = [s['total_pnl'] for s in daily_summary]
            
            fig.add_trace(go.Scatter(
                x=dates,
                y=total_pnl,
                mode='lines+markers',
                name='日次損益',
                line=dict(color='#FF6B35', width=2),
                marker=dict(size=6)
            ))
            
            fig.update_layout(
                title="日次損益推移",
                xaxis_title="日付",
                yaxis_title="損益 (JPY)",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#e8e8e8'),
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # サマリーテーブル
            st.markdown("#### 📊 日次サマリー")
            
            df_summary = pd.DataFrame(daily_summary)
            df_summary.columns = ['日付', '取引数', '取引量', '損益', '手数料', '勝ち', '負け', '買い', '売り', '勝率']
            
            # 数値フォーマット
            df_summary['損益'] = df_summary['損益'].apply(lambda x: f"¥{x:,.0f}")
            df_summary['手数料'] = df_summary['手数料'].apply(lambda x: f"¥{x:,.0f}")
            df_summary['勝率'] = df_summary['勝率'].apply(lambda x: f"{x:.1f}%")
            
            st.dataframe(df_summary, use_container_width=True, height=300)
        else:
            st.info("分析データがありません")
        
        # 戦略別パフォーマンス
        strategy_performance = log_reader.get_strategy_performance(days=30)
        
        if strategy_performance:
            st.markdown("#### 🎯 戦略別パフォーマンス")
            
            strategy_data = list(strategy_performance.values())
            df_strategy = pd.DataFrame(strategy_data)
            
            if not df_strategy.empty:
                # 戦略別損益チャート
                fig = go.Figure(data=[
                    go.Bar(
                        x=df_strategy['strategy'],
                        y=df_strategy['total_pnl'],
                        text=df_strategy['total_pnl'].apply(lambda x: f"¥{x:,.0f}"),
                        textposition='auto',
                        marker_color=['#FF6B35' if x >= 0 else '#FF4757' for x in df_strategy['total_pnl']]
                    )
                ])
                
                fig.update_layout(
                    title="戦略別総損益",
                    xaxis_title="戦略",
                    yaxis_title="損益 (JPY)",
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#e8e8e8'),
                    height=400
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # 戦略パフォーマンステーブル
                df_display = df_strategy[['strategy', 'total_trades', 'win_rate', 'total_pnl', 'total_fees']].copy()
                df_display.columns = ['戦略', '取引数', '勝率', '総損益', '総手数料']
                df_display['勝率'] = df_display['勝率'].apply(lambda x: f"{x:.1f}%")
                df_display['総損益'] = df_display['総損益'].apply(lambda x: f"¥{x:,.0f}")
                df_display['総手数料'] = df_display['総手数料'].apply(lambda x: f"¥{x:,.0f}")
                
                st.dataframe(df_display, use_container_width=True)
    
    with tab4:
        st.markdown("### ⚙️ システム状態監視")
        
        # システム状態メトリクス
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # アラートシステム状態
            alert_status = "稼働中" if alert_system.running else "停止中"
            alert_color = "positive" if alert_system.running else "negative"
            
            st.markdown(create_metric_card(
                "アラートシステム",
                alert_status,
                icon="fas fa-bell",
                delta_color=alert_color
            ), unsafe_allow_html=True)
        
        with col2:
            # ログファイル数
            try:
                log_files = list(log_reader.log_path.glob("*.csv")) + list(log_reader.log_path.glob("*.jsonl"))
                log_count = len(log_files)
            except:
                log_count = 0
            
            st.markdown(create_metric_card(
                "ログファイル数",
                str(log_count),
                icon="fas fa-file-alt"
            ), unsafe_allow_html=True)
        
        with col3:
            # システム稼働時間（簡易版）
            uptime = "稼働中"
            st.markdown(create_metric_card(
                "システム状態",
                uptime,
                icon="fas fa-server",
                delta_color="positive"
            ), unsafe_allow_html=True)
        
        with col4:
            # メモリ使用量（簡易版）
            memory_usage = "正常"
            st.markdown(create_metric_card(
                "メモリ状態",
                memory_usage,
                icon="fas fa-memory",
                delta_color="positive"
            ), unsafe_allow_html=True)
        
        # システム制御
        st.markdown("#### 🛠️ システム制御")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🚀 アラートシステム開始"):
                if not alert_system.running:
                    alert_system.start()
                    st.success("アラートシステムを開始しました")
                else:
                    st.info("アラートシステムは既に稼働中です")
        
        with col2:
            if st.button("⏹️ アラートシステム停止"):
                if alert_system.running:
                    alert_system.stop()
                    st.success("アラートシステムを停止しました")
                else:
                    st.info("アラートシステムは既に停止中です")
        
        with col3:
            if st.button("🧪 テストアラート送信"):
                alert_system.send_alert(
                    alert_system.AlertType.SYSTEM_ERROR,
                    alert_system.AlertLevel.INFO,
                    "テストアラート",
                    "これはテスト用のアラートです",
                    {"test": True}
                )
                st.success("テストアラートを送信しました")
        
        # ログファイル一覧
        st.markdown("#### 📄 ログファイル一覧")
        
        try:
            log_files = []
            
            # CSVファイル
            for csv_file in log_reader.log_path.glob("*.csv"):
                stat = csv_file.stat()
                log_files.append({
                    'ファイル名': csv_file.name,
                    'タイプ': 'CSV',
                    'サイズ': f"{stat.st_size / 1024:.1f} KB",
                    '更新日時': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
            
            # JSONLファイル
            for jsonl_file in log_reader.log_path.glob("*.jsonl"):
                stat = jsonl_file.stat()
                log_files.append({
                    'ファイル名': jsonl_file.name,
                    'タイプ': 'JSONL',
                    'サイズ': f"{stat.st_size / 1024:.1f} KB",
                    '更新日時': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
            
            if log_files:
                df_logs = pd.DataFrame(log_files)
                st.dataframe(df_logs, use_container_width=True)
            else:
                st.info("ログファイルが見つかりません")
                
        except Exception as e:
            st.error(f"ログファイル一覧取得エラー: {e}")


def risk_management_page(data: Dict[str, Any]):
    """リスク管理ページ（リファクタリング版）"""
    create_section_header(
        "リスク管理", 
        "shield-alt", 
        "ポジションサイズ・損切り・利確・ドローダウン制限の管理"
    )

    # リスク管理システムを初期化
    try:
        from backend.risk_manager import RiskManager
        risk_manager = RiskManager()
    except Exception as e:
        show_error_message(f"リスク管理システムの初期化に失敗しました: {str(e)}")
        return

    # 現在の口座情報とポジション情報を取得
    balance = data.get('balance', {})
    positions = data.get('positions', [])
    risk_metrics = data.get('risk_metrics', {})
    
    # account_info形式に変換
    account_info = {
        'total_balance': balance.get('total_jpy', 0),
        'available_balance': balance.get('available_jpy', 0),
        'margin_level': 1.0  # 現物取引なので100%
    }
    
    # タブで機能を分割
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 リスク監視", "💰 ポジションサイズ", "⛔ 損切り・利確", "📉 ドローダウン制限", "🔢 取引限度"
    ])

    with tab1:
        risk_monitoring_section(risk_manager, account_info, positions, data)
    
    with tab2:
        position_sizing_section(risk_manager)
    
    with tab3:
        stop_loss_take_profit_section(risk_manager)
    
    with tab4:
        drawdown_limits_section(risk_manager, account_info)
    
    with tab5:
        trading_limits_section(risk_manager)

def risk_monitoring_section(risk_manager: 'RiskManager', account_info: Dict[str, Any], 
                           positions: List[Dict[str, Any]], data: Dict[str, Any]):
    """リスク監視セクション"""
    st.markdown("### 📊 リアルタイムリスク監視")
    
    # 現在のリスク状況をチェック
    can_trade, risk_reason = risk_manager.check_risk_limits(account_info, positions)
    
    # リスク状況の表示
    col1, col2 = st.columns(2)
    
    with col1:
        # 取引可能状況
        status_color = "🟢" if can_trade else "🔴"
        status_text = "正常" if can_trade else "制限中"
        
        st.markdown(create_metric_card(
            "🚦 取引状況", 
            f"{status_color} {status_text}",
            delta=risk_reason if not can_trade else "全ての制限をクリア",
            delta_color="normal" if can_trade else "inverse",
            icon="traffic-light"
        ), unsafe_allow_html=True)
    
    with col2:
        # 現在のポジション数
        current_positions = len(positions)
        max_positions = risk_manager.risk_config.get('max_open_positions', 3)
        
        st.markdown(create_metric_card(
            "📊 ポジション数", 
            f"{current_positions} / {max_positions}",
            delta=f"{max_positions - current_positions} 残り" if current_positions < max_positions else "上限到達",
            delta_color="normal" if current_positions < max_positions else "inverse",
            icon="chart-bar"
        ), unsafe_allow_html=True)

    # ドローダウン監視
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # 最大ドローダウン
        max_dd_limit = risk_manager.risk_config.get('max_drawdown_percentage', 0.20) * 100
        current_dd = risk_manager.current_drawdown * 100
        
        st.markdown(create_metric_card(
            "📉 現在DD", 
            f"{current_dd:.2f}%",
            delta=f"限界: {max_dd_limit:.1f}%",
            delta_color="normal" if current_dd < max_dd_limit * 0.8 else "inverse",
            icon="chart-line-down"
        ), unsafe_allow_html=True)
    
    with col2:
        # 日次取引数
        daily_trades = risk_manager.daily_trades
        max_daily = risk_manager.risk_config.get('max_daily_trades', 10)
        
        st.markdown(create_metric_card(
            "🔢 今日の取引", 
            f"{daily_trades} / {max_daily}",
            delta=f"{max_daily - daily_trades} 残り",
            delta_color="normal" if daily_trades < max_daily * 0.8 else "inverse",
            icon="calculator"
        ), unsafe_allow_html=True)
    
    with col3:
        # 証拠金維持率
        margin_level = account_info.get('margin_level', 1.0) * 100
        margin_call = risk_manager.risk_config.get('margin_call_percentage', 0.05) * 100
        
        st.markdown(create_metric_card(
            "💳 証拠金維持率", 
            f"{margin_level:.1f}%",
            delta=f"警告: {margin_call:.1f}%以下",
            delta_color="normal" if margin_level > margin_call * 2 else "inverse",
            icon="credit-card"
        ), unsafe_allow_html=True)

    # ポートフォリオメトリクス
    st.markdown("### 📈 ポートフォリオメトリクス")
    
    metrics = risk_manager.calculate_portfolio_metrics()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(create_metric_card(
            "🎯 勝率", 
            f"{metrics['win_rate'] * 100:.1f}%",
            icon="target"
        ), unsafe_allow_html=True)
    
    with col2:
        st.markdown(create_metric_card(
            "💰 プロフィットファクター", 
            f"{metrics['profit_factor']:.2f}",
            icon="coins"
        ), unsafe_allow_html=True)
    
    with col3:
        st.markdown(create_metric_card(
            "📊 シャープレシオ", 
            f"{metrics['sharpe_ratio']:.2f}",
            icon="chart-area"
        ), unsafe_allow_html=True)
    
    with col4:
        st.markdown(create_metric_card(
            "🔢 総取引数", 
            f"{metrics['total_trades']}",
            icon="list-ol"
        ), unsafe_allow_html=True)

    # リスクアラート
    if not can_trade:
        st.error(f"⚠️ **取引制限中**: {risk_reason}")
    
    # ドローダウン警告
    if current_dd > max_dd_limit * 0.8:
        st.warning(f"⚠️ **ドローダウン警告**: 現在 {current_dd:.2f}% （限界: {max_dd_limit:.1f}%）")

def position_sizing_section(risk_manager: 'RiskManager'):
    """ポジションサイズ管理セクション"""
    st.markdown("### 💰 ポジションサイズ管理")
    
    # 現在の設定を取得
    sizing_config = risk_manager.risk_config.get('position_sizing', {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📊 現在の設定")
        
        # ポジションサイジング方式
        current_method = sizing_config.get('method', 'fixed_percentage')
        method_names = {
            'fixed_percentage': '固定パーセンテージ',
            'kelly': 'ケリー基準',
            'fixed_amount': '固定額'
        }
        
        st.markdown(create_metric_card(
            "⚙️ 計算方式", 
            method_names.get(current_method, current_method),
            icon="cog"
        ), unsafe_allow_html=True)
        
        # リスク率
        risk_per_trade = sizing_config.get('risk_per_trade', 0.02) * 100
        st.markdown(create_metric_card(
            "📊 リスク率", 
            f"{risk_per_trade:.1f}%",
            delta="1取引あたりの最大リスク",
            icon="percentage"
        ), unsafe_allow_html=True)
        
        # 最大ポジションサイズ
        max_position = sizing_config.get('max_position_size', 0.1)
        st.markdown(create_metric_card(
            "📏 最大ポジション", 
            f"{max_position:.4f} BTC",
            icon="ruler"
        ), unsafe_allow_html=True)
    
    with col2:
        st.markdown("#### ⚙️ 設定変更")
        
        # ポジションサイジング方式の選択
        new_method = st.selectbox(
            "計算方式",
            ['fixed_percentage', 'kelly', 'fixed_amount'],
            format_func=lambda x: method_names.get(x, x),
            index=['fixed_percentage', 'kelly', 'fixed_amount'].index(current_method)
        )
        
        # リスク率の設定
        new_risk_rate = st.slider(
            "リスク率 (%)",
            min_value=0.1,
            max_value=10.0,
            value=risk_per_trade,
            step=0.1,
            help="1取引あたりの最大リスク（総資産に対する割合）"
        )
        
        # 最大ポジションサイズ
        new_max_position = st.number_input(
            "最大ポジションサイズ (BTC)",
            min_value=0.0001,
            max_value=10.0,
            value=max_position,
            step=0.0001,
            format="%.4f"
        )
        
        # 設定保存ボタン
        if st.button("💾 ポジションサイズ設定を保存", key="save_position_sizing"):
            try:
                # 設定を更新
                config_manager = get_config_manager()
                config_manager.set('risk_management.position_sizing.method', new_method)
                config_manager.set('risk_management.position_sizing.risk_per_trade', new_risk_rate / 100)
                config_manager.set('risk_management.position_sizing.max_position_size', new_max_position)
                
                st.success("✅ ポジションサイズ設定を保存しました")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 設定保存に失敗しました: {str(e)}")

def stop_loss_take_profit_section(risk_manager: 'RiskManager'):
    """損切り・利確設定セクション"""
    st.markdown("### ⛔ 損切り・利確設定")
    
    # 説明を追加
    st.info("""
    📌 **重要な用語説明**
    - **損切り（ストップロス）** = 損失が拡大する前に自動で売却する機能（赤字を最小限に抑える）
    - **利確（テイクプロフィット）** = 利益が出ている時に自動で売却する機能（利益を確定させる）
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🛑 損切り設定（ストップロス）")
        st.markdown("*⚠️ 損失を限定するための自動売却設定*")
        
        sl_config = risk_manager.risk_config.get('stop_loss', {})
        
        # ストップロス有効化
        sl_enabled = st.checkbox(
            "損切りを有効化（推奨: ON）",
            value=sl_config.get('enabled', True),
            help="損失が拡大する前に自動的にポジションを閉じます"
        )
        
        if sl_enabled:
            # 計算方式
            sl_method = st.selectbox(
                "損切り計算方式",
                ['percentage', 'atr', 'fixed_amount'],
                format_func=lambda x: {
                    'percentage': '📊 パーセンテージ（%で指定）',
                    'atr': '📈 ATR（ボラティリティ基準）',
                    'fixed_amount': '💰 固定額（円で指定）'
                }.get(x, x),
                index=['percentage', 'atr', 'fixed_amount'].index(sl_config.get('method', 'percentage')),
                key="sl_method"
            )
            
            if sl_method == 'percentage':
                sl_percentage = st.slider(
                    "損切り率（エントリー価格からの下落%）",
                    min_value=0.5,
                    max_value=10.0,
                    value=sl_config.get('percentage', 0.02) * 100,
                    step=0.1,
                    help="例：2%なら、100万円で買った場合98万円で自動売却",
                    key="sl_percentage"
                )
                st.caption(f"💡 {sl_percentage}%下がったら自動損切り実行")
            elif sl_method == 'atr':
                sl_atr_multiplier = st.slider(
                    "ATR倍率（価格変動幅の何倍で損切り）",
                    min_value=1.0,
                    max_value=5.0,
                    value=sl_config.get('atr_multiplier', 2.0),
                    step=0.1,
                    help="ATR（価格変動幅）の倍率で損切り価格を決定",
                    key="sl_atr"
                )
                st.caption(f"💡 価格変動幅の{sl_atr_multiplier}倍下がったら損切り")
            else:  # fixed_amount
                sl_fixed_amount = st.number_input(
                    "固定損失額（この金額の損失で自動売却）",
                    min_value=1000,
                    max_value=1000000,
                    value=sl_config.get('fixed_amount', 50000),
                    step=1000,
                    help="例：50,000円なら、5万円の損失で自動売却",
                    key="sl_fixed"
                )
                st.caption(f"💡 {format_jpy(sl_fixed_amount)}の損失で自動損切り")
    
    with col2:
        st.markdown("#### 🎯 利確設定（テイクプロフィット）")
        st.markdown("*💰 利益を確定するための自動売却設定*")
        
        tp_config = risk_manager.risk_config.get('take_profit', {})
        
        # テイクプロフィット有効化
        tp_enabled = st.checkbox(
            "利確を有効化（推奨: ON）",
            value=tp_config.get('enabled', True),
            help="利益が出ている時に自動的にポジションを閉じて利益を確定します"
        )
        
        if tp_enabled:
            # 計算方式
            tp_method = st.selectbox(
                "利確計算方式",
                ['risk_reward', 'percentage', 'fixed_amount'],
                format_func=lambda x: {
                    'risk_reward': '⚖️ リスクリワード比（損失の何倍で利確）',
                    'percentage': '📊 パーセンテージ（%で指定）',
                    'fixed_amount': '💰 固定額（円で指定）'
                }.get(x, x),
                index=['risk_reward', 'percentage', 'fixed_amount'].index(tp_config.get('method', 'risk_reward')),
                key="tp_method"
            )
            
            if tp_method == 'risk_reward':
                tp_ratio = st.slider(
                    "リスクリワード比（損失の何倍で利確するか）",
                    min_value=1.0,
                    max_value=5.0,
                    value=tp_config.get('risk_reward_ratio', 2.0),
                    step=0.1,
                    help="例：2.0なら、損切り額の2倍の利益で自動売却",
                    key="tp_ratio"
                )
                st.caption(f"💡 損失額の{tp_ratio}倍の利益で自動利確")
            elif tp_method == 'percentage':
                tp_percentage = st.slider(
                    "利確率（エントリー価格からの上昇%）",
                    min_value=1.0,
                    max_value=20.0,
                    value=tp_config.get('percentage', 0.04) * 100,
                    step=0.1,
                    help="例：4%なら、100万円で買った場合104万円で自動売却",
                    key="tp_percentage"
                )
                st.caption(f"💡 {tp_percentage}%上がったら自動利確実行")
            else:  # fixed_amount
                tp_fixed_amount = st.number_input(
                    "固定利益額（この金額の利益で自動売却）",
                    min_value=1000,
                    max_value=1000000,
                    value=tp_config.get('fixed_amount', 100000),
                    step=1000,
                    help="例：100,000円なら、10万円の利益で自動売却",
                    key="tp_fixed"
                )
                st.caption(f"💡 {format_jpy(tp_fixed_amount)}の利益で自動利確")

    # 設定保存ボタン
    if st.button("💾 損切り・利確設定を保存", key="save_sl_tp"):
        try:
            config_manager = get_config_manager()
            
            # ストップロス設定
            config_manager.set('risk_management.stop_loss.enabled', sl_enabled)
            if sl_enabled:
                config_manager.set('risk_management.stop_loss.method', sl_method)
                if sl_method == 'percentage':
                    config_manager.set('risk_management.stop_loss.percentage', sl_percentage / 100)
                elif sl_method == 'atr':
                    config_manager.set('risk_management.stop_loss.atr_multiplier', sl_atr_multiplier)
                else:
                    config_manager.set('risk_management.stop_loss.fixed_amount', sl_fixed_amount)
            
            # テイクプロフィット設定
            config_manager.set('risk_management.take_profit.enabled', tp_enabled)
            if tp_enabled:
                config_manager.set('risk_management.take_profit.method', tp_method)
                if tp_method == 'risk_reward':
                    config_manager.set('risk_management.take_profit.risk_reward_ratio', tp_ratio)
                elif tp_method == 'percentage':
                    config_manager.set('risk_management.take_profit.percentage', tp_percentage / 100)
                else:
                    config_manager.set('risk_management.take_profit.fixed_amount', tp_fixed_amount)
            
            st.success("✅ 損切り・利確設定を保存しました")
            st.rerun()
        except Exception as e:
            st.error(f"❌ 設定保存に失敗しました: {str(e)}")

def drawdown_limits_section(risk_manager: 'RiskManager', account_info: Dict[str, Any]):
    """ドローダウン制限セクション"""
    st.markdown("### 📉 ドローダウン制限")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📊 現在の状況")
        
        # 現在のドローダウン
        current_dd = risk_manager.current_drawdown * 100
        max_dd_limit = risk_manager.risk_config.get('max_drawdown_percentage', 0.20) * 100
        
        st.markdown(create_metric_card(
            "📉 現在のDD", 
            f"{current_dd:.2f}%",
            delta=f"限界まで {max_dd_limit - current_dd:.2f}%",
            delta_color="normal" if current_dd < max_dd_limit * 0.8 else "inverse",
            icon="chart-line-down"
        ), unsafe_allow_html=True)
        
        # ピーク残高
        peak_balance = risk_manager.peak_balance
        st.markdown(create_metric_card(
            "🏔️ ピーク残高", 
            format_jpy(peak_balance),
            icon="mountain"
        ), unsafe_allow_html=True)
        
        # 現在残高
        current_balance = account_info.get('total_balance', 0)
        st.markdown(create_metric_card(
            "💰 現在残高", 
            format_jpy(current_balance),
            delta=f"{((current_balance / peak_balance - 1) * 100):+.2f}%" if peak_balance > 0 else "",
            delta_color="normal" if current_balance >= peak_balance else "inverse",
            icon="wallet"
        ), unsafe_allow_html=True)
    
    with col2:
        st.markdown("#### ⚙️ 制限設定")
        
        # 最大ドローダウン制限
        new_max_dd = st.slider(
            "最大ドローダウン制限 (%)",
            min_value=5.0,
            max_value=50.0,
            value=max_dd_limit,
            step=1.0,
            help="この値を超えるとすべての取引が停止されます"
        )
        
        # 証拠金維持率制限
        margin_call_limit = risk_manager.risk_config.get('margin_call_percentage', 0.05) * 100
        new_margin_call = st.slider(
            "証拠金維持率制限 (%)",
            min_value=1.0,
            max_value=20.0,
            value=margin_call_limit,
            step=0.5,
            help="この値以下になると取引が停止されます"
        )
        
        # 緊急停止ボタン
        st.markdown("#### 🚨 緊急制御")
        
        if st.button("🚨 すべての取引を緊急停止", key="emergency_stop"):
            st.warning("⚠️ 緊急停止機能は実装予定です")
        
        # 設定保存
        if st.button("💾 ドローダウン制限を保存", key="save_drawdown"):
            try:
                config_manager = get_config_manager()
                config_manager.set('risk_management.max_drawdown_percentage', new_max_dd / 100)
                config_manager.set('risk_management.margin_call_percentage', new_margin_call / 100)
                
                st.success("✅ ドローダウン制限を保存しました")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 設定保存に失敗しました: {str(e)}")

def trading_limits_section(risk_manager: 'RiskManager'):
    """取引限度設定セクション"""
    st.markdown("### 🔢 取引限度設定")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📊 現在の制限")
        
        # 最大ポジション数
        max_positions = risk_manager.risk_config.get('max_open_positions', 3)
        st.markdown(create_metric_card(
            "📊 最大ポジション数", 
            f"{max_positions}",
            icon="chart-bar"
        ), unsafe_allow_html=True)
        
        # 日次最大取引数
        max_daily_trades = risk_manager.risk_config.get('max_daily_trades', 10)
        st.markdown(create_metric_card(
            "🔢 日次最大取引数", 
            f"{max_daily_trades}",
            icon="calculator"
        ), unsafe_allow_html=True)
        
        # 今日の取引数
        daily_trades = risk_manager.daily_trades
        st.markdown(create_metric_card(
            "📅 今日の取引数", 
            f"{daily_trades} / {max_daily_trades}",
            delta=f"{max_daily_trades - daily_trades} 残り",
            delta_color="normal" if daily_trades < max_daily_trades else "inverse",
            icon="calendar-day"
        ), unsafe_allow_html=True)
    
    with col2:
        st.markdown("#### ⚙️ 制限変更")
        
        # 最大ポジション数の設定
        new_max_positions = st.slider(
            "最大同時ポジション数",
            min_value=1,
            max_value=10,
            value=max_positions,
            step=1,
            help="同時に保有できる最大ポジション数"
        )
        
        # 日次最大取引数の設定
        new_max_daily = st.slider(
            "日次最大取引数",
            min_value=1,
            max_value=50,
            value=max_daily_trades,
            step=1,
            help="1日に実行できる最大取引数"
        )
        
        # 取引時間制限（将来実装）
        st.markdown("#### ⏰ 取引時間制限（将来実装）")
        
        trading_start = st.time_input(
            "取引開始時刻",
            value=datetime.strptime("09:00", "%H:%M").time(),
            disabled=True
        )
        
        trading_end = st.time_input(
            "取引終了時刻",
            value=datetime.strptime("17:00", "%H:%M").time(),
            disabled=True
        )
        
        # 設定保存
        if st.button("💾 取引限度を保存", key="save_trading_limits"):
            try:
                config_manager = get_config_manager()
                config_manager.set('risk_management.max_open_positions', new_max_positions)
                config_manager.set('risk_management.max_daily_trades', new_max_daily)
                
                st.success("✅ 取引限度設定を保存しました")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 設定保存に失敗しました: {str(e)}")


def backtest_settings_section():
    """⑥バックテスト設定層"""
    st.markdown("#### ⚙️ バックテスト設定")
    
    # 戦略マネージャーをインポート
    try:
        from backend.strategy import get_strategy_manager
        strategy_manager = get_strategy_manager()
        available_strategies = strategy_manager.get_available_strategies()
    except Exception as e:
        st.error(f"戦略マネージャーの初期化に失敗: {e}")
        available_strategies = [
            {'id': 'ma_cross_strategy', 'name': '移動平均クロス戦略', 'parameters': {'short_period': 5, 'long_period': 20}},
            {'id': 'macd_rsi_strategy', 'name': 'MACD + RSI戦略', 'parameters': {'rsi_period': 14, 'macd_fast': 12}},
            {'id': 'grid_trading_strategy', 'name': 'グリッドトレーディング', 'parameters': {'grid_size': 0.01, 'grid_levels': 10}}
        ]
    
    # === 基本設定エリア ===
    st.markdown("**📋 基本設定**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # 戦略選択
        strategy_options = {s['id']: s['name'] for s in available_strategies}
        selected_strategy = st.selectbox(
            "🎯 戦略",
            options=list(strategy_options.keys()),
            format_func=lambda x: strategy_options.get(x, x),
            help="バックテストする取引戦略を選択してください"
        )
    
    with col2:
        # 通貨ペア選択
        symbol = st.selectbox(
            "💱 通貨ペア",
            options=['BTC_JPY', 'ETH_JPY', 'XRP_JPY', 'LTC_JPY', 'BCH_JPY'],
            index=0,
            help="バックテスト対象の通貨ペアを選択してください"
        )
    
    with col3:
        # 時間枠選択
        timeframe = st.selectbox(
            "⏰ 時間枠",
            options=['1min', '5min', '15min', '1hour', '4hour', '1day'],
            index=3,  # デフォルト: 1hour
            help="分析する価格データの時間間隔を選択してください"
        )
    
    st.markdown("---")
    
    # === 期間設定エリア ===
    st.markdown("**📅 期間設定**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        start_date = st.date_input(
            "📊 開始日",
            value=datetime.now() - timedelta(days=30),
            max_value=datetime.now() - timedelta(days=1),
            help="バックテストの開始日を選択してください"
        )
    
    with col2:
        end_date = st.date_input(
            "🏁 終了日",
            value=datetime.now() - timedelta(days=1),
            min_value=start_date,
            max_value=datetime.now(),
            help="バックテストの終了日を選択してください"
        )
    
    with col3:
        # 期間情報表示
        period_days = (end_date - start_date).days
        st.metric(
            "📈 期間",
            f"{period_days}日間",
            f"{period_days * 24 if timeframe == '1hour' else period_days}データポイント予想"
        )
    
    st.markdown("---")
    
    # === 詳細設定エリア ===
    with st.expander("⚙️ 詳細設定", expanded=True):
        
        # 資金設定
        st.markdown("**💰 資金設定**")
        col1, col2 = st.columns(2)
        
        with col1:
            initial_capital = st.number_input(
                "初期資金 (円)",
                min_value=100000,
                value=1000000,
                step=100000,
                help="バックテスト開始時の資金額を設定してください"
            )
        
        with col2:
            position_size_pct = st.slider(
                "ポジションサイズ (%)",
                min_value=1,
                max_value=100,
                value=10,
                help="1回の取引で使用する資金の割合を設定してください"
            )
        
        st.markdown("**💸 コスト設定**")
        col1, col2 = st.columns(2)
        
        with col1:
            commission = st.number_input(
                "手数料 (%)",
                min_value=0.0,
                max_value=1.0,
                value=0.09,
                step=0.01,
                format="%.3f",
                help="取引手数料率を設定してください（GMOコイン: 0.09%）"
            )
        
        with col2:
            slippage = st.number_input(
                "スリッページ (%)",
                min_value=0.0,
                max_value=1.0,
                value=0.01,
                step=0.01,
                format="%.3f",
                help="価格スリッページを設定してください"
            )
    
    # === 戦略パラメータ設定 ===
    selected_strategy_info = next((s for s in available_strategies if s['id'] == selected_strategy), None)
    strategy_params = {}
    
    if selected_strategy_info and selected_strategy_info.get('parameters'):
        st.markdown("---")
        st.markdown("**🎛️ 戦略パラメータ**")
        
        # パラメータを2列で表示
        param_items = list(selected_strategy_info['parameters'].items())
        cols = st.columns(min(2, len(param_items)))
        
        for i, (param_name, default_value) in enumerate(param_items):
            with cols[i % 2]:
                param_display_name = param_name.replace('_', ' ').title()
                
                if isinstance(default_value, int):
                    strategy_params[param_name] = st.number_input(
                        param_display_name,
                        value=default_value,
                        step=1,
                        help=f"戦略パラメータ: {param_name}"
                    )
                elif isinstance(default_value, float):
                    strategy_params[param_name] = st.number_input(
                        param_display_name,
                        value=default_value,
                        step=0.01,
                        format="%.4f",
                        help=f"戦略パラメータ: {param_name}"
                    )
                elif isinstance(default_value, bool):
                    strategy_params[param_name] = st.checkbox(
                        param_display_name,
                        value=default_value,
                        help=f"戦略パラメータ: {param_name}"
                    )
                else:
                    strategy_params[param_name] = st.text_input(
                        param_display_name,
                        value=str(default_value),
                        help=f"戦略パラメータ: {param_name}"
                    )
    
    st.markdown("---")
    
    # === 実行ボタンエリア ===
    col1, col2, col3 = st.columns([2, 1, 2])
    
    with col2:
        if st.button(
            "🚀 バックテスト実行",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.backtest_running
        ):
            # バックテスト実行
            run_backtest(
                strategy_id=selected_strategy,
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                position_size_pct=position_size_pct,
                commission=commission,
                slippage=slippage,
                strategy_params=strategy_params
            )
    
    # 実行中の表示
    if st.session_state.backtest_running:
        st.info("⏳ バックテストを実行中です...")
        st.progress(0.5)


def run_backtest(strategy_id: str, symbol: str, timeframe: str, start_date, end_date,
                initial_capital: float, position_size_pct: int, commission: float,
                slippage: float, strategy_params: dict):
    """バックテストを実行"""
    
    st.session_state.backtest_running = True
    
    try:
        with st.spinner("🔄 バックテストを実行中..."):
            # バックエンドモジュールをインポート
            from backend.backtester import Backtester
            from backend.config_manager import get_config_manager
            
            # 設定を一時的に更新
            config = get_config_manager()
            config.set('backtest.initial_capital', initial_capital)
            config.set('backtest.commission.taker_fee', commission / 100)
            config.set('backtest.slippage.market', slippage / 100)
            
            # バックテスターを作成
            backtester = Backtester()
            
            # バックテストを実行
            result = backtester.run_backtest(
                strategy_id=strategy_id,
                start_date=datetime.combine(start_date, datetime.min.time()),
                end_date=datetime.combine(end_date, datetime.max.time()),
                symbol=symbol,
                interval=timeframe,
                parameters=strategy_params
            )
            
            if result:
                st.session_state.backtest_result = result
                st.success("✅ バックテストが完了しました！")
                st.info("💡 「結果表示」タブで詳細な結果を確認できます。")
            else:
                st.error("❌ バックテストの実行に失敗しました")
                
    except ImportError as e:
        st.error(f"❌ バックエンドモジュールのインポートに失敗: {e}")
        st.info("💡 デモモードでバックテスト結果を生成します...")
        # デモ結果を生成
        st.session_state.backtest_result = generate_demo_backtest_result(
            strategy_id, symbol, start_date, end_date, initial_capital
        )
        st.success("✅ デモバックテストが完了しました！")
        
    except Exception as e:
        st.error(f"❌ バックテスト実行エラー: {e}")
        
    finally:
        st.session_state.backtest_running = False


def generate_demo_backtest_result(strategy_id: str, symbol: str, start_date, end_date, initial_capital: float) -> dict:
    """デモ用のバックテスト結果を生成"""
    import numpy as np
    
    # 基本設定
    days = (end_date - start_date).days
    total_return = np.random.uniform(-20, 50)  # -20%から+50%
    win_rate = np.random.uniform(45, 75)  # 45%から75%
    total_trades = np.random.randint(20, 100)
    
    # 計算値
    final_balance = initial_capital * (1 + total_return / 100)
    max_drawdown = np.random.uniform(5, 30)
    sharpe_ratio = np.random.uniform(0.5, 2.5)
    profit_factor = np.random.uniform(1.1, 2.8)
    
    # 資産曲線生成
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    returns = np.random.normal(total_return / days / 100, 0.02, len(dates))
    equity_values = [initial_capital]
    
    for daily_return in returns[1:]:
        equity_values.append(equity_values[-1] * (1 + daily_return))
    
    return {
        'strategy_id': strategy_id,
        'symbol': symbol,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'summary': {
            'initial_capital': initial_capital,
            'final_balance': final_balance,
            'total_return': final_balance - initial_capital,
            'total_return_pct': total_return,
            'max_drawdown_pct': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'profit_factor': profit_factor,
            'win_rate': win_rate,
            'total_trades': total_trades,
            'winning_trades': int(total_trades * win_rate / 100),
            'losing_trades': int(total_trades * (100 - win_rate) / 100),
            'total_fees': final_balance * 0.001  # 手数料概算
        },
        'equity_curve': {
            'timestamps': [d.strftime('%Y-%m-%d') for d in dates],
            'equity': equity_values[:len(dates)],
            'balance': equity_values[:len(dates)]
        },
        'trades': [],  # 簡略化のため空
        'buy_hold_comparison': {
            'total_return_pct': np.random.uniform(10, 40),
            'sharpe_ratio': np.random.uniform(0.8, 1.5),
            'max_drawdown_pct': np.random.uniform(15, 35)
        }
    }


def backtest_results_section():
    """⑦バックテスト結果層"""
    st.markdown("#### 📊 バックテスト結果")
    
    if st.session_state.backtest_result is None:
        st.info("👈 左の「バックテスト設定」タブでバックテストを実行してください。")
        
        # サンプル結果表示ボタン
        if st.button("🎭 デモ結果を表示", help="サンプルのバックテスト結果を表示します"):
            st.session_state.backtest_result = generate_demo_backtest_result(
                'ma_cross_strategy', 'BTC_JPY', 
                datetime.now() - timedelta(days=30), 
                datetime.now() - timedelta(days=1), 
                1000000
            )
            st.rerun()
        return
    
    result = st.session_state.backtest_result
    summary = result.get('summary', {})
    
    # === サマリーメトリクス ===
    st.markdown("**📈 パフォーマンスサマリー**")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_return_pct = summary.get('total_return_pct', 0)
        color = "normal" if total_return_pct >= 0 else "inverse"
        delta_color = "positive" if total_return_pct >= 0 else "negative"
        
        st.markdown(create_metric_card(
            "💰 総収益率",
            f"{total_return_pct:.2f}%",
            delta=f"{'+' if total_return_pct >= 0 else ''}{total_return_pct:.2f}%",
            delta_color=delta_color,
            icon="📈" if total_return_pct >= 0 else "📉"
        ), unsafe_allow_html=True)
    
    with col2:
        final_balance = summary.get('final_balance', 0)
        initial_capital = summary.get('initial_capital', 1000000)
        profit = final_balance - initial_capital
        
        st.markdown(create_metric_card(
            "💵 最終資産",
            format_jpy(final_balance),
            delta=f"{'+' if profit >= 0 else ''}{format_jpy(profit)}",
            delta_color="positive" if profit >= 0 else "negative",
            icon="💎"
        ), unsafe_allow_html=True)
    
    with col3:
        sharpe_ratio = summary.get('sharpe_ratio', 0)
        sharpe_color = "positive" if sharpe_ratio > 1.0 else "warning" if sharpe_ratio > 0.5 else "negative"
        
        st.markdown(create_metric_card(
            "📊 シャープレシオ",
            f"{sharpe_ratio:.2f}",
            delta="優秀" if sharpe_ratio > 1.0 else "良好" if sharpe_ratio > 0.5 else "要改善",
            delta_color=sharpe_color,
            icon="⭐"
        ), unsafe_allow_html=True)
    
    with col4:
        max_dd = summary.get('max_drawdown_pct', 0)
        dd_color = "positive" if max_dd < 10 else "warning" if max_dd < 20 else "negative"
        
        st.markdown(create_metric_card(
            "📉 最大DD",
            f"{max_dd:.1f}%",
            delta="低リスク" if max_dd < 10 else "中リスク" if max_dd < 20 else "高リスク",
            delta_color=dd_color,
            icon="🛡️"
        ), unsafe_allow_html=True)
    
    st.markdown("---")
    
    # === 詳細メトリクス ===
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🎯 取引統計**")
        
        trade_metrics = {
            '総取引数': f"{summary.get('total_trades', 0)}回",
            '勝率': f"{summary.get('win_rate', 0):.1f}%",
            '勝ちトレード': f"{summary.get('winning_trades', 0)}回",
            '負けトレード': f"{summary.get('losing_trades', 0)}回",
            'プロフィットファクター': f"{summary.get('profit_factor', 0):.2f}",
            '総手数料': format_jpy(summary.get('total_fees', 0))
        }
        
        for key, value in trade_metrics.items():
            st.markdown(f"""
            <div style="display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid var(--border-color);">
                <span style="color: var(--text-color-secondary);">{key}</span>
                <span style="color: var(--text-color); font-weight: 600;">{value}</span>
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("**🆚 Buy & Hold比較**")
        
        buy_hold = result.get('buy_hold_comparison', {})
        strategy_return = summary.get('total_return_pct', 0)
        buy_hold_return = buy_hold.get('total_return_pct', 0)
        outperforms = strategy_return > buy_hold_return
        
        comparison_metrics = {
            '戦略リターン': f"{strategy_return:.2f}%",
            'Buy & Holdリターン': f"{buy_hold_return:.2f}%",
            'アウトパフォーム': f"{'+' if outperforms else ''}{strategy_return - buy_hold_return:.2f}%",
            '戦略シャープレシオ': f"{summary.get('sharpe_ratio', 0):.2f}",
            'Buy & Holdシャープレシオ': f"{buy_hold.get('sharpe_ratio', 0):.2f}",
            '判定': "🎉 戦略の勝利!" if outperforms else "😞 Buy & Holdの勝利"
        }
        
        for key, value in comparison_metrics.items():
            color = "var(--success-color)" if key == "判定" and outperforms else "var(--error-color)" if key == "判定" else "var(--text-color)"
            st.markdown(f"""
            <div style="display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid var(--border-color);">
                <span style="color: var(--text-color-secondary);">{key}</span>
                <span style="color: {color}; font-weight: 600;">{value}</span>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # === 資産曲線グラフ ===
    display_backtest_charts(result)
    
    # === 詳細データ表示 ===
    with st.expander("📋 詳細データ"):
        st.json(result, expanded=False)


def display_backtest_charts(result: dict):
    """バックテスト結果のチャートを表示"""
    st.markdown("**📈 資産推移チャート**")
    
    equity_curve = result.get('equity_curve', {})
    timestamps = equity_curve.get('timestamps', [])
    equity_values = equity_curve.get('equity', [])
    
    if not timestamps or not equity_values:
        st.warning("📊 資産曲線データがありません")
        return
    
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        
        # 日付を変換
        dates = pd.to_datetime(timestamps)
        
        # Buy & Hold曲線を計算
        buy_hold_comparison = result.get('buy_hold_comparison', {})
        buy_hold_return = buy_hold_comparison.get('total_return_pct', 0)
        initial_value = equity_values[0] if equity_values else 1000000
        
        # Buy & Hold曲線（単純な線形増加として近似）
        buy_hold_values = [initial_value * (1 + (buy_hold_return / 100) * i / len(equity_values)) 
                          for i in range(len(equity_values))]
        
        # グラフ作成
        fig = go.Figure()
        
        # 戦略の資産曲線
        fig.add_trace(go.Scatter(
            x=dates,
            y=equity_values,
            mode='lines',
            name='戦略',
            line=dict(color='#00d4aa', width=3),
            hovertemplate='<b>戦略</b><br>日付: %{x}<br>資産: ¥%{y:,.0f}<extra></extra>'
        ))
        
        # Buy & Hold曲線
        fig.add_trace(go.Scatter(
            x=dates,
            y=buy_hold_values,
            mode='lines',
            name='Buy & Hold',
            line=dict(color='#ff6b6b', width=2, dash='dash'),
            hovertemplate='<b>Buy & Hold</b><br>日付: %{x}<br>資産: ¥%{y:,.0f}<extra></extra>'
        ))
        
        # レイアウト設定
        fig.update_layout(
            title="資産推移比較",
            xaxis_title="日付",
            yaxis_title="資産額 (円)",
            template="plotly_dark",
            hovermode="x unified",
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01
            ),
            height=500
        )
        
        # Y軸フォーマット
        fig.update_yaxis(tickformat=",.0f")
        
        st.plotly_chart(fig, use_container_width=True)
        
        # ドローダウンチャート
        st.markdown("**📉 ドローダウン分析**")
        
        # ドローダウン計算
        peak = pd.Series(equity_values).expanding().max()
        drawdown = (pd.Series(equity_values) - peak) / peak * 100
        
        fig_dd = go.Figure()
        
        fig_dd.add_trace(go.Scatter(
            x=dates,
            y=drawdown,
            mode='lines',
            fill='tonegative',
            name='ドローダウン',
            line=dict(color='#ff6b6b', width=2),
            fillcolor='rgba(255, 107, 107, 0.3)',
            hovertemplate='<b>ドローダウン</b><br>日付: %{x}<br>DD: %{y:.1f}%<extra></extra>'
        ))
        
        fig_dd.update_layout(
            title="ドローダウン推移",
            xaxis_title="日付",
            yaxis_title="ドローダウン (%)",
            template="plotly_dark",
            height=300
        )
        
        st.plotly_chart(fig_dd, use_container_width=True)
        
    except ImportError:
        st.error("📊 Plotlyが利用できません。グラフ表示にはplotlyのインストールが必要です。")
    except Exception as e:
        st.error(f"📊 グラフ表示エラー: {e}")


if __name__ == "__main__":
    main()
