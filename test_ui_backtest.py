#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
sys.path.append('.')

def test_ui_backtest():
    """UIと同じ方法でバックテストを実行してテスト"""
    print("🔄 UI同様のバックテスト実行テスト開始")
    
    try:
        # UIのrun_backtest関数と同じ処理を実行
        from backend.backtester import Backtester
        from backend.config_manager import get_config_manager
        from datetime import datetime, timedelta
        
        print("✅ バックエンドモジュールのインポート成功")
        
        # テストパラメータ（UIのデフォルト値）
        strategy_id = 'ma_cross'
        symbol = 'BTC_JPY'
        timeframe = '15min'
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now() - timedelta(days=1)
        initial_capital = 1000000.0
        commission = 0.05  # 0.05%
        slippage = 0.01    # 0.01%
        strategy_params = {'short_period': 5, 'long_period': 20}
        
        print(f"📋 テスト設定:")
        print(f"  戦略: {strategy_id}")
        print(f"  期間: {start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}")
        print(f"  初期資金: {initial_capital:,.0f}円")
        
        # 設定を一時的に更新
        config = get_config_manager()
        config.set('backtest.initial_capital', initial_capital)
        config.set('backtest.commission.taker_fee', commission / 100)
        config.set('backtest.slippage.market', slippage / 100)
        
        print("✅ 設定更新完了")
        
        # バックテスターを作成
        backtester = Backtester()
        print("✅ バックテスター作成完了")
        
        # バックテストを実行
        print("🚀 バックテスト実行中...")
        result = backtester.run_backtest(
            strategy_id=strategy_id,
            start_date=start_date,
            end_date=end_date,
            symbol=symbol,
            interval=timeframe,
            parameters=strategy_params
        )
        
        if result:
            print("🎉 バックテスト実行成功！")
            
            # 結果の詳細表示
            summary = result.get('summary', {})
            buy_hold = result.get('buy_hold_comparison', {})
            
            print(f"\n📊 結果サマリー:")
            print(f"  総収益率: {summary.get('total_return_pct', 0):.2f}%")
            print(f"  最終資産: {summary.get('final_balance', 0):,.0f}円")
            print(f"  シャープレシオ: {summary.get('sharpe_ratio', 0):.2f}")
            print(f"  最大DD: {summary.get('max_drawdown_pct', 0):.2f}%")
            print(f"  取引数: {summary.get('total_trades', 0)}回")
            
            print(f"\n🆚 Buy & Hold比較:")
            print(f"  戦略リターン: {summary.get('total_return_pct', 0):.2f}%")
            print(f"  Buy & Holdリターン: {buy_hold.get('total_return_pct', 0):.2f}%")
            print(f"  Buy & Holdシャープレシオ: {buy_hold.get('sharpe_ratio', 0):.2f}")
            print(f"  Buy & Hold最大DD: {buy_hold.get('max_drawdown_pct', 0):.2f}%")
            
            # Buy & Hold単体結果をチェック
            print(f"\n🔍 Buy & Hold詳細データ:")
            for key, value in buy_hold.items():
                print(f"  {key}: {value}")
                
            return result
        else:
            print("❌ バックテスト実行失敗")
            return None
            
    except ImportError as e:
        print(f"❌ インポートエラー: {e}")
        print("💡 この場合、UIはデモモードに切り替わります")
        return None
        
    except Exception as e:
        print(f"❌ バックテスト実行エラー: {e}")
        return None

def test_demo_mode():
    """デモモードの結果も確認"""
    print("\n" + "="*60)
    print("🎭 デモモード結果テスト")
    print("="*60)
    
    try:
        import numpy as np
        import pandas as pd
        from datetime import datetime, timedelta
        
        # UIのgenerate_demo_backtest_result関数と同じ処理
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now() - timedelta(days=1)
        initial_capital = 1000000.0
        
        days = (end_date - start_date).days
        total_return = np.random.uniform(-20, 50)
        win_rate = np.random.uniform(45, 75)
        total_trades = np.random.randint(20, 100)
        
        final_balance = initial_capital * (1 + total_return / 100)
        max_drawdown = np.random.uniform(5, 30)
        sharpe_ratio = np.random.uniform(0.5, 2.5)
        
        print(f"📊 デモ結果:")
        print(f"  総収益率: {total_return:.2f}%")
        print(f"  最終資産: {final_balance:,.0f}円")
        print(f"  シャープレシオ: {sharpe_ratio:.2f}")
        print(f"  最大DD: {max_drawdown:.2f}%")
        print(f"  取引数: {total_trades}回")
        
        # Buy & Hold比較
        buy_hold_return = np.random.uniform(10, 40)
        buy_hold_sharpe = np.random.uniform(0.8, 1.5)
        buy_hold_dd = np.random.uniform(15, 35)
        
        print(f"\n🆚 デモのBuy & Hold比較:")
        print(f"  Buy & Holdリターン: {buy_hold_return:.2f}%")
        print(f"  Buy & Holdシャープレシオ: {buy_hold_sharpe:.2f}")
        print(f"  Buy & Hold最大DD: {buy_hold_dd:.2f}%")
        
        print("\n💡 これがUIで表示されているなら、デモモードです")
        
    except Exception as e:
        print(f"❌ デモモードテストエラー: {e}")

if __name__ == "__main__":
    result = test_ui_backtest()
    test_demo_mode()
    
    print("\n" + "="*60)
    if result:
        print("✅ 結論: UIは実際のバックテストを実行可能")
        print("🔍 UIの結果が異なる場合は、設定やパラメータの違いが原因")
    else:
        print("❌ 結論: UIはデモモードで動作している可能性が高い")
        print("🔧 バックエンドモジュールの問題を修正する必要あり") 