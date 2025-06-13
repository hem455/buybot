"""
Streamlit UI メインアプリケーション

GMOコイン自動売買システムのWebインターフェース
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import asyncio
from typing import Dict, Any, Optional

# バックエンドモジュールのインポート
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from backend.config_manager import get_config_manager
from backend.logger import get_logger
from backend.strategy import get_strategy_manager
from backend.backtester import Backtester, BenchmarkComparator
from backend.backtester.validator import BacktestValidator
from backend.data_fetcher import GMOCoinRESTFetcher
from backend.risk_manager import RiskManager
from backend.order_executor import OrderExecutor

# 同じディレクトリのui_helpersをインポート
try:
    from ui_helpers import display_benchmark_comparison, display_backtest_warnings
except ImportError:
    # ui_helpersが見つからない場合のダミー関数
    def display_benchmark_comparison(result):
        st.info("ベンチマーク比較機能は準備中です")
    
    def display_backtest_warnings(result):
        st.info("警告表示機能は準備中です")

# ページ設定
st.set_page_config(
    page_title="GMOコイン自動売買システム",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# セッション状態の初期化
if 'bot_running' not in st.session_state:
    st.session_state.bot_running = False
if 'backtest_result' not in st.session_state:
    st.session_state.backtest_result = None
if 'current_tab' not in st.session_state:
    st.session_state.current_tab = "バックテスト"


def main():
    """メインアプリケーション"""
    # タイトル
    st.title("🚀 GMOコイン自動売買システム")
    
    # タブ作成
    tab1, tab2 = st.tabs(["📊 バックテスト", "🔴 リアルタイムダッシュボード"])
    
    with tab1:
        backtest_page()
    
    with tab2:
        realtime_dashboard_page()


def backtest_page():
    """バックテストページ"""
    st.header("バックテスト")
    
    # 設定エリア
    with st.expander("バックテスト設定", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # 戦略選択
            strategy_manager = get_strategy_manager()
            available_strategies = strategy_manager.get_available_strategies()
            strategy_options = {s['id']: s['name'] for s in available_strategies}
            
            selected_strategy = st.selectbox(
                "戦略選択",
                options=list(strategy_options.keys()),
                format_func=lambda x: strategy_options[x]
            )
            
            # 初期資金
            initial_capital = st.number_input(
                "初期資金 (JPY)",
                min_value=100000,
                value=1000000,
                step=100000
            )
        
        with col2:
            # 期間設定
            start_date = st.date_input(
                "開始日",
                value=datetime.now() - timedelta(days=30)
            )
            
            end_date = st.date_input(
                "終了日",
                value=datetime.now()
            )
            
            # 時間間隔
            interval = st.selectbox(
                "時間間隔",
                options=['1min', '5min', '15min', '1hour', '4hour', '1day'],
                index=3  # デフォルトは1hour
            )
        
        with col3:
            # 手数料設定
            commission_rate = st.number_input(
                "手数料率 (%)",
                min_value=0.0,
                value=0.09,
                step=0.01,
                format="%.2f"
            ) / 100
            
            # 戦略パラメータ
            st.subheader("戦略パラメータ")
            strategy_params = {}
            
            selected_strategy_info = next((s for s in available_strategies if s['id'] == selected_strategy), None)
            if selected_strategy_info:
                default_params = selected_strategy_info.get('parameters', {})
                
                for param_name, default_value in default_params.items():
                    if isinstance(default_value, int):
                        strategy_params[param_name] = st.number_input(
                            param_name,
                            value=default_value,
                            step=1
                        )
                    elif isinstance(default_value, float):
                        strategy_params[param_name] = st.number_input(
                            param_name,
                            value=default_value,
                            step=0.01,
                            format="%.2f"
                        )
    
    # バックテスト実行ボタン
    if st.button("バックテスト実行", type="primary"):
        with st.spinner("バックテスト実行中..."):
            # バックテストを実行
            result = run_backtest_sync(
                selected_strategy,
                start_date,
                end_date,
                interval,
                initial_capital,
                commission_rate,
                strategy_params
            )
            
            if result:
                st.session_state.backtest_result = result
                st.success("バックテストが完了しました！")
            else:
                st.error("バックテストの実行に失敗しました")
    
    # 結果表示
    if st.session_state.backtest_result:
        display_backtest_results(st.session_state.backtest_result)


def run_backtest_sync(strategy_id: str, start_date, end_date, interval: str,
                     initial_capital: float, commission_rate: float,
                     strategy_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """バックテストを同期的に実行"""
    try:
        # 設定を一時的に更新
        config = get_config_manager()
        config.set('backtest.initial_capital', initial_capital)
        config.set('backtest.commission.taker_fee', commission_rate)
        
        # バックテスターを作成
        backtester = Backtester()
        
        # バックテストを実行
        result = backtester.run_backtest(
            strategy_id=strategy_id,
            start_date=datetime.combine(start_date, datetime.min.time()),
            end_date=datetime.combine(end_date, datetime.max.time()),
            interval=interval,
            parameters=strategy_params
        )
        
        return result
        
    except Exception as e:
        st.error(f"エラー: {str(e)}")
        return None


def display_backtest_results(result: Dict[str, Any]):
    """バックテスト結果を表示"""
    st.header("📈 バックテスト結果")
    
    # サマリー情報
    summary = result.get('summary', {})
    
    # Buy & Hold比較
    st.subheader("🆚 Buy & Hold戦略との比較")
    display_benchmark_comparison(result)
    
    # 警告表示
    st.subheader("🚨 バックテスト結果の警告")
    display_backtest_warnings(result)
    
    # メトリクス表示
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "最終残高",
            f"¥{summary.get('final_balance', 0):,.0f}",
            f"{summary.get('total_return', 0):,.0f}"
        )
        st.metric(
            "総リターン",
            f"{summary.get('total_return_pct', 0):.2f}%"
        )
    
    with col2:
        st.metric(
            "総取引数",
            f"{summary.get('total_trades', 0)}"
        )
        st.metric(
            "勝率",
            f"{summary.get('win_rate', 0):.1f}%"
        )
    
    with col3:
        st.metric(
            "プロフィットファクター",
            f"{summary.get('profit_factor', 0):.2f}"
        )
        st.metric(
            "シャープレシオ",
            f"{summary.get('sharpe_ratio', 0):.2f}"
        )
    
    with col4:
        st.metric(
            "最大ドローダウン",
            f"{summary.get('max_drawdown_pct', 0):.1f}%"
        )
        st.metric(
            "総手数料",
            f"¥{summary.get('total_fees', 0):,.0f}"
        )
    
    # 資産曲線グラフ
    st.subheader("資産推移")
    equity_curve = result.get('equity_curve', {})
    
    if equity_curve.get('timestamps'):
        fig = go.Figure()
        
        # 残高の推移
        fig.add_trace(go.Scatter(
            x=equity_curve['timestamps'],
            y=equity_curve['balance'],
            mode='lines',
            name='残高',
            line=dict(color='blue', width=2)
        ))
        
        # 評価額の推移
        fig.add_trace(go.Scatter(
            x=equity_curve['timestamps'],
            y=equity_curve['equity'],
            mode='lines',
            name='評価額',
            line=dict(color='green', width=2)
        ))
        
        fig.update_layout(
            title="資産推移",
            xaxis_title="日時",
            yaxis_title="金額 (JPY)",
            height=500,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # 取引履歴
    st.subheader("取引履歴")
    trades = result.get('trades', [])
    
    if trades:
        # DataFrameに変換
        trades_df = pd.DataFrame(trades)
        
        # 表示用に整形
        display_columns = ['timestamp', 'type', 'side', 'price', 'size', 'pnl', 'commission']
        available_columns = [col for col in display_columns if col in trades_df.columns]
        
        st.dataframe(
            trades_df[available_columns],
            use_container_width=True,
            hide_index=True
        )
        
        # 取引統計
        with st.expander("詳細統計"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**勝ちトレード**")
                st.write(f"- 回数: {summary.get('winning_trades', 0)}")
                st.write(f"- 平均利益: ¥{summary.get('average_win', 0):,.0f}")
                st.write(f"- 最大利益: ¥{summary.get('largest_win', 0):,.0f}")
            
            with col2:
                st.write("**負けトレード**")
                st.write(f"- 回数: {summary.get('losing_trades', 0)}")
                st.write(f"- 平均損失: ¥{summary.get('average_loss', 0):,.0f}")
                st.write(f"- 最大損失: ¥{summary.get('largest_loss', 0):,.0f}")


def realtime_dashboard_page():
    """リアルタイムダッシュボードページ"""
    st.header("リアルタイムダッシュボード")
    
    # システムコントロール
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        if st.button(
            "🟢 システム起動" if not st.session_state.bot_running else "🔴 システム停止",
            type="primary" if not st.session_state.bot_running else "secondary"
        ):
            st.session_state.bot_running = not st.session_state.bot_running
            
            if st.session_state.bot_running:
                st.success("システムを起動しました")
                # TODO: 実際のボット起動処理
            else:
                st.warning("システムを停止しました")
                # TODO: 実際のボット停止処理
    
    with col2:
        if st.button("🔄 データ更新"):
            st.rerun()
    
    with col3:
        # システム状態表示
        if st.session_state.bot_running:
            st.success("🟢 システム稼働中")
        else:
            st.info("⚪ システム停止中")
    
    # 口座情報
    st.subheader("💰 口座情報")
    display_account_info()
    
    # ポジション情報
    st.subheader("📊 ポジション情報")
    display_positions()
    
    # 戦略情報
    st.subheader("🎯 戦略情報")
    display_strategy_info()
    
    # 最新シグナル
    st.subheader("📡 最新シグナル")
    display_latest_signals()


def display_account_info():
    """口座情報を表示"""
    # TODO: 実際のAPIから取得
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("総資産", "¥1,234,567")
    with col2:
        st.metric("実現損益（本日）", "¥12,345", "1.23%")
    with col3:
        st.metric("含み損益", "¥-2,345", "-0.19%")
    with col4:
        st.metric("証拠金維持率", "523%")


def display_positions():
    """ポジション情報を表示"""
    # TODO: 実際のAPIから取得
    positions_data = [
        {
            "通貨ペア": "BTC/JPY",
            "方向": "買い",
            "数量": 0.01,
            "平均取得価格": "¥4,500,000",
            "現在価格": "¥4,520,000",
            "評価損益": "¥200",
            "評価損益率": "+0.44%"
        }
    ]
    
    if positions_data:
        df = pd.DataFrame(positions_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("現在ポジションはありません")


def display_strategy_info():
    """戦略情報を表示"""
    strategy_manager = get_strategy_manager()
    
    if strategy_manager.active_strategy:
        strategy_info = strategy_manager.get_active_strategy_info()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**稼働中の戦略**: {strategy_info.get('name', 'なし')}")
            st.write(f"**説明**: {strategy_info.get('description', '')}")
        
        with col2:
            st.write("**パラメータ**:")
            params = strategy_info.get('parameters', {})
            for key, value in params.items():
                st.write(f"- {key}: {value}")
    else:
        st.info("戦略が設定されていません")


def display_latest_signals():
    """最新シグナルを表示"""
    # TODO: 実際のシグナル履歴から取得
    signals_data = [
        {
            "時刻": "2024-01-01 12:00:00",
            "シグナル": "BUY",
            "価格": "¥4,500,000",
            "理由": "ゴールデンクロス"
        }
    ]
    
    if signals_data:
        df = pd.DataFrame(signals_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("シグナル履歴がありません")


# エラーハンドリング
def handle_error(func):
    """エラーハンドリングデコレータ"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            st.error(f"エラーが発生しました: {str(e)}")
            return None
    return wrapper


if __name__ == "__main__":
    main()
