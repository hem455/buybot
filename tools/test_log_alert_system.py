#!/usr/bin/env python3
"""
ログ&アラートシステムテストスクリプト

TradeLogReaderとAlertSystemの動作確認を行います
"""

import sys
import os
from pathlib import Path
import time
import json
from datetime import datetime, timedelta

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from backend.utils.trade_log_reader import get_trade_log_reader
from backend.utils.alert_system import get_alert_system, AlertType, AlertLevel
from backend.logger import log_trade, get_logger

# ロガー設定
logger = get_logger()

def test_trade_log_system():
    """取引ログシステムのテスト"""
    print("\n🧪 取引ログシステムテスト開始")
    
    # サンプル取引ログを生成
    sample_trades = [
        {
            'timestamp': (datetime.now() - timedelta(hours=1)).isoformat(),
            'pair': 'BTC_JPY',
            'side': 'BUY',
            'quantity': 0.001,
            'price': 4500000,
            'fee': 45,
            'realized_pnl': 0,
            'order_id': 'test_order_001',
            'execution_id': 'test_exec_001',
            'strategy': 'MA Cross'
        },
        {
            'timestamp': (datetime.now() - timedelta(minutes=30)).isoformat(),
            'pair': 'BTC_JPY', 
            'side': 'SELL',
            'quantity': 0.001,
            'price': 4520000,
            'fee': 45.2,
            'realized_pnl': 19800,
            'order_id': 'test_order_002',
            'execution_id': 'test_exec_002',
            'strategy': 'MA Cross'
        }
    ]
    
    print("📊 サンプル取引ログを生成中...")
    for trade in sample_trades:
        log_trade(trade)
    
    # ログリーダーでテスト
    log_reader = get_trade_log_reader()
    
    print("📋 取引ログ取得テスト...")
    recent_trades = log_reader.get_recent_trades(limit=10)
    print(f"取得した取引数: {len(recent_trades)}")
    
    # 検証アサーション: 取引ログの正確性確認
    assert isinstance(recent_trades, list), "取引ログはリスト形式である必要があります"
    assert len(recent_trades) >= len(sample_trades), f"最低{len(sample_trades)}件の取引が取得されるべきです"
    
    if recent_trades:
        latest_trade = recent_trades[0]
        required_fields = ['timestamp', 'pair', 'side', 'quantity', 'price', 'fee']
        for field in required_fields:
            assert field in latest_trade, f"取引ログに必須フィールド'{field}'が不足しています"
        assert latest_trade['quantity'] > 0, "取引量は正の値である必要があります"
        assert latest_trade['price'] > 0, "取引価格は正の値である必要があります"
    
    # 日次サマリーテスト
    print("📈 日次サマリー生成テスト...")
    daily_summary = log_reader.get_daily_summary(days=7)
    print(f"日次サマリー数: {len(daily_summary)}")
    
    # 検証アサーション: 日次サマリーの正確性確認
    assert isinstance(daily_summary, list), "日次サマリーはリスト形式である必要があります"
    if daily_summary:
        today_summary = daily_summary[0]
        summary_fields = ['date', 'total_trades', 'total_volume', 'realized_pnl', 'total_fees']
        for field in summary_fields:
            assert field in today_summary, f"日次サマリーに必須フィールド'{field}'が不足しています"
        assert today_summary['total_trades'] >= 0, "総取引数は非負値である必要があります"
    
    # 戦略別パフォーマンステスト
    print("🎯 戦略別パフォーマンス分析テスト...")
    strategy_performance = log_reader.get_strategy_performance(days=7)
    print(f"分析対象戦略数: {len(strategy_performance)}")
    
    # 検証アサーション: 戦略パフォーマンスの正確性確認
    assert isinstance(strategy_performance, dict), "戦略パフォーマンスは辞書形式である必要があります"
    if strategy_performance:
        for strategy_name, performance in strategy_performance.items():
            assert isinstance(strategy_name, str), "戦略名は文字列である必要があります"
            assert isinstance(performance, dict), "パフォーマンスデータは辞書形式である必要があります"
            perf_fields = ['total_trades', 'win_rate', 'total_pnl']
            for field in perf_fields:
                assert field in performance, f"戦略'{strategy_name}'のパフォーマンスに'{field}'が不足しています"
    
    print("✅ 取引ログシステムテスト完了")

def test_alert_system():
    """アラートシステムのテスト"""
    print("\n🚨 アラートシステムテスト開始")
    
    alert_system = get_alert_system()
    
    # アラートシステム開始
    print("🚀 アラートシステム開始...")
    alert_system.start()
    
    try:
        time.sleep(1)  # 少し待機
        
        # 各種アラートのテスト
        test_alerts = [
            {
                'type': AlertType.TRADE_EXECUTED,
                'level': AlertLevel.INFO,
                'title': 'テスト取引実行',
                'message': 'BUY 0.001 BTC @ ¥4,500,000',
                'data': {'side': 'BUY', 'quantity': 0.001, 'price': 4500000}
            },
            {
                'type': AlertType.STRATEGY_ERROR,
                'level': AlertLevel.WARNING,
                'title': 'テスト戦略エラー',
                'message': 'MA Cross戦略でデータ不足エラーが発生しました',
                'data': {'strategy': 'MA Cross', 'error': 'データ不足'}
            },
            {
                'type': AlertType.SYSTEM_ERROR,
                'level': AlertLevel.ERROR,
                'title': 'テストシステムエラー',
                'message': 'APIレート制限に達しました',
                'data': {'api': 'GMOCoin', 'status_code': 429}
            },
            {
                'type': AlertType.HIGH_DRAWDOWN,
                'level': AlertLevel.CRITICAL,
                'title': 'テスト高ドローダウン',
                'message': 'ドローダウンが5%を超えました',
                'data': {'current_drawdown': 5.2, 'max_allowed': 5.0}
            }
        ]
        
        print("📤 テストアラート送信中...")
        for i, alert_data in enumerate(test_alerts):
            print(f"  {i+1}. {alert_data['title']}")
            alert_system.send_alert(
                alert_data['type'],
                alert_data['level'],
                alert_data['title'],
                alert_data['message'],
                alert_data['data'],
                strategy_id='test_strategy' if 'strategy' in alert_data['data'] else None
            )
            time.sleep(0.5)  # 少し間隔を空ける
        
        time.sleep(2)  # 処理待機
        
        # アラート取得テスト
        print("📥 アラート取得テスト...")
        recent_alerts = alert_system.get_recent_alerts(limit=10)
        print(f"取得したアラート数: {len(recent_alerts)}")
        
        # 検証アサーション: アラートシステムの正確性確認
        assert isinstance(recent_alerts, list), "アラートは リスト形式である必要があります"
        assert len(recent_alerts) >= len(test_alerts), f"最低{len(test_alerts)}件のアラートが取得されるべきです"
        
        if recent_alerts:
            latest_alert = recent_alerts[0]
            alert_fields = ['timestamp', 'type', 'level', 'title', 'message']
            for field in alert_fields:
                assert field in latest_alert, f"アラートに必須フィールド'{field}'が不足しています"
            assert latest_alert['title'], "アラートタイトルは空でないことが必要です"
        
        for alert in recent_alerts:
            print(f"  - [{alert['level'].upper()}] {alert['title']}")
        
        # アラート統計テスト
        print("📊 アラート統計テスト...")
        alert_stats = alert_system.get_alert_statistics(days=1)
        print(f"統計情報: {json.dumps(alert_stats, indent=2, ensure_ascii=False)}")
        
        # 検証アサーション: アラート統計の正確性確認
        assert isinstance(alert_stats, dict), "アラート統計は辞書形式である必要があります"
        expected_stats = ['total_alerts', 'alerts_by_level', 'alerts_by_type']
        for stat in expected_stats:
            assert stat in alert_stats, f"アラート統計に'{stat}'が不足しています"
        
    finally:
        # アラートシステム停止（エラー発生時も確実に実行）
        try:
            print("⏹️ アラートシステム停止...")
            alert_system.stop()
            print("✅ アラートシステムテスト完了")
        except Exception as stop_error:
            print(f"⚠️ アラートシステム停止中にエラー: {stop_error}")
            logger.error(f"アラートシステム停止エラー: {stop_error}")

def test_system_integration():
    """システム統合テスト"""
    print("\n🔗 システム統合テスト開始")
    
    # 両システムを同時に使用
    log_reader = get_trade_log_reader()
    alert_system = get_alert_system()
    
    # アラートシステム開始
    alert_system.start()
    
    try:
        # 取引実行をシミュレート
        trade_data = {
            'timestamp': datetime.now().isoformat(),
            'pair': 'BTC_JPY',
            'side': 'BUY',
            'quantity': 0.002,
            'price': 4550000,
            'fee': 91,
            'realized_pnl': 0,
            'order_id': 'integration_test_001',
            'execution_id': 'integration_exec_001',
            'strategy': 'Integration Test'
        }
        
        print("📊 統合テスト用取引ログ記録...")
        log_trade(trade_data)
        
        print("🚨 取引実行アラート送信...")
        alert_system.alert_trade_executed(trade_data, 'Integration Test')
        
        time.sleep(1)
        
        # 結果確認
        recent_trades = log_reader.get_recent_trades(limit=5)
        recent_alerts = alert_system.get_recent_alerts(limit=5)
        
        print(f"📋 最新取引ログ数: {len(recent_trades)}")
        print(f"🚨 最新アラート数: {len(recent_alerts)}")
        
        # 検証アサーション: 統合テストの正確性確認
        assert len(recent_trades) > 0, "統合テスト後に取引ログが存在する必要があります"
        assert len(recent_alerts) > 0, "統合テスト後にアラートが存在する必要があります"
        
        # 統合テストで生成したデータの検証
        integration_trades = [t for t in recent_trades if t.get('strategy') == 'Integration Test']
        assert len(integration_trades) > 0, "Integration Test戦略の取引が記録されている必要があります"
        
    finally:
        # アラートシステム停止（エラー発生時も確実に実行）
        try:
            alert_system.stop()
            print("✅ システム統合テスト完了")
        except Exception as stop_error:
            print(f"⚠️ 統合テスト停止中にエラー: {stop_error}")
            logger.error(f"システム統合テスト停止エラー: {stop_error}")

def main():
    """メイン関数"""
    print("🎯 GMOコイン自動売買システム - ログ&アラートシステムテスト")
    print("=" * 60)
    
    try:
        # 各テストを実行
        test_trade_log_system()
        test_alert_system()
        test_system_integration()
        
        print("\n🎉 全テスト完了！")
        print("=" * 60)
        print("📋 取引ログシステム: ✅ 正常動作")
        print("🚨 アラートシステム: ✅ 正常動作")
        print("🔗 システム統合: ✅ 正常動作")
        print("\n💡 Streamlitアプリで「📋 ログ&アラート」ページを確認してください")
        
    except Exception as e:
        print(f"\n❌ テスト中にエラーが発生しました: {e}")
        logger.error(f"ログ&アラートシステムテストエラー: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 