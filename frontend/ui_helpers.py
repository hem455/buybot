from typing import Dict, Any
import streamlit as st
import pandas as pd
from backend.backtester.benchmark import BenchmarkComparator

def display_benchmark_comparison(result: Dict[str, Any]):
    """Buy & Hold戦略との比較を表示"""
    # データ取得期間を特定
    if 'equity_curve' in result and result['equity_curve'].get('timestamps'):
        start_date = result['equity_curve']['timestamps'][0]
        end_date = result['equity_curve']['timestamps'][-1]
    else:
        return
    
    # ベンチマーク計算
    comparator = BenchmarkComparator()
    
    # Buy & Hold結果を計算（実際のデータを使用）
    # ※ここは実装時に実際のOHLCVデータを取得する必要あり
    buy_hold_result = {
        'total_return_pct': 50.0,  # 仮の値
        'sharpe_ratio': 0.8,
        'max_drawdown_pct': 25.0
    }
    
    # 比較結果
    comparison = comparator.compare_with_strategy(result, buy_hold_result)
    
    # 表示
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "戦略リターン",
            f"{comparison['strategy']['total_return_pct']:.1f}%",
            f"{comparison['return_difference_pct']:+.1f}%"
        )
    
    with col2:
        st.metric(
            "戦略シャープレシオ",
            f"{comparison['strategy']['sharpe_ratio']:.2f}",
            f"{comparison['sharpe_ratio_difference']:+.2f}"
        )
    
    with col3:
        if comparison['strategy_beats_buy_hold']:
            st.success("✅ Buy & Holdに勝利！")
        else:
            st.error("❌ Buy & Holdに敗北...")
    
    # 詳細比較テーブル
    comparison_df = pd.DataFrame({
        '指標': ['総リターン', 'シャープレシオ', '最大DD', '勝率', '取引数'],
        '戦略': [
            f"{comparison['strategy']['total_return_pct']:.1f}%",
            f"{comparison['strategy']['sharpe_ratio']:.2f}",
            f"{comparison['strategy']['max_drawdown_pct']:.1f}%",
            f"{comparison['strategy']['win_rate']:.1f}%",
            f"{comparison['strategy']['total_trades']}"
        ],
        'Buy & Hold': [
            f"{comparison['buy_and_hold']['total_return_pct']:.1f}%",
            f"{comparison['buy_and_hold']['sharpe_ratio']:.2f}",
            f"{comparison['buy_and_hold']['max_drawdown_pct']:.1f}%",
            "N/A",
            "1"
        ]
    })
    
    st.dataframe(comparison_df, hide_index=True)
    

def display_backtest_warnings(result: Dict[str, Any]):
    """バックテスト結果の警告を表示"""
    from backend.backtester.validator import BacktestValidator
    
    validator = BacktestValidator()
    
    # ベンチマーク結果を取得
    if 'buy_hold_comparison' in result:
        benchmark_result = result['buy_hold_comparison']
    else:
        # デフォルト値
        benchmark_result = {
            'total_return_pct': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown_pct': 0.0
        }
    
    # 警告を生成
    warnings = validator.validate_results(result, benchmark_result)
    
    # 重大な警告
    if warnings['critical']:
        st.error("🚨 **重大な問題が検出されました！**")
        for warning in warnings['critical']:
            st.error(warning)
    
    # 警告
    if warnings['warning']:
        st.warning("⚠️ **注意すべき点があります**")
        for warning in warnings['warning']:
            st.warning(warning)
    
    # 情報
    if warnings['info']:
        for info in warnings['info']:
            st.info(info)
    
    # 改善提案
    if warnings['critical'] or warnings['warning']:
        recommendations = validator.generate_recommendations(warnings)
        if recommendations:
            with st.expander("💡 改善提案"):
                for rec in recommendations:
                    st.write(rec)
