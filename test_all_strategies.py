#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
sys.path.append('.')
from backend.backtester import Backtester
from backend.strategy.strategy_manager import StrategyManager
from datetime import datetime, timedelta

def test_all_strategies():
    """すべての戦略をテストしてBuy & Hold比較を検証"""
    print("🔄 全戦略テスト開始")
    
    try:
        # Backtesterとストラテジーマネージャーを初期化
        backtester = Backtester()
        strategy_manager = StrategyManager()
        
        print("✅ 初期化成功")
        
        # 利用可能な戦略を取得
        available_strategies = strategy_manager.get_available_strategies()
        print(f"📋 利用可能な戦略数: {len(available_strategies)}")
        
        for strategy in available_strategies:
            print(f"  - {strategy['id']}: {strategy['name']}")
        
        # テスト期間設定（短期で確実にデータがある期間）
        end_date = datetime.now() - timedelta(days=1)
        start_date = end_date - timedelta(days=7)  # 1週間
        
        print(f"\n📅 テスト期間: {start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}")
        
        results = {}
        
        # 各戦略をテスト
        for strategy_info in available_strategies:
            strategy_id = strategy_info['id']
            strategy_name = strategy_info['name']
            
            print(f"\n🚀 {strategy_name} ({strategy_id}) テスト中...")
            
            # 戦略に応じたパラメータ設定
            if strategy_id == 'simple_ma_cross':
                params = {'short_period': 5, 'long_period': 20}
            elif strategy_id == 'macd_rsi':
                params = {'rsi_oversold': 30, 'rsi_overbought': 70, 'macd_threshold': 0}
            elif strategy_id == 'grid_trading':
                params = {'grid_size': 5, 'grid_spacing': 1000, 'initial_capital': 1000000}
            elif strategy_id == 'ml_based':
                params = {'model_type': 'random_forest', 'lookback_period': 20}
            else:
                params = {}
            
            try:
                result = backtester.run_backtest(
                    strategy_id=strategy_id,
                    start_date=start_date,
                    end_date=end_date,
                    symbol='BTC_JPY',
                    interval='15min',
                    parameters=params
                )
                
                if result:
                    print(f"✅ {strategy_name} - バックテスト成功!")
                    
                    # 戦略結果表示
                    summary = result.get('summary', {})
                    print(f"  💰 初期資金: {summary.get('initial_capital', 0):,.0f}円")
                    print(f"  💵 最終資産: {summary.get('final_capital', 0):,.0f}円")
                    print(f"  📈 総収益率: {summary.get('total_return_pct', 0):.2f}%")
                    print(f"  📉 最大DD: {summary.get('max_drawdown_pct', 0):.2f}%")
                    print(f"  🎯 取引数: {summary.get('total_trades', 0)}")
                    print(f"  ⭐ シャープレシオ: {summary.get('sharpe_ratio', 0):.2f}")
                    
                    # Buy & Hold比較結果確認
                    buy_hold = result.get('buy_hold_comparison', {})
                    if buy_hold:
                        print(f"  🆚 Buy & Hold比較:")
                        print(f"    📊 Buy&Hold収益率: {buy_hold.get('total_return_pct', 0):.2f}%")
                        print(f"    ⭐ Buy&Holdシャープレシオ: {buy_hold.get('sharpe_ratio', 0):.2f}")
                        print(f"    📉 Buy&Hold最大DD: {buy_hold.get('max_drawdown_pct', 0):.2f}%")
                        
                        # 勝敗判定
                        strategy_return = summary.get('total_return_pct', 0)
                        buyhold_return = buy_hold.get('total_return_pct', 0)
                        if strategy_return > buyhold_return:
                            print(f"    🏆 戦略の勝利！差分: +{strategy_return - buyhold_return:.2f}%")
                        else:
                            print(f"    😞 Buy&Holdの勝利！差分: {strategy_return - buyhold_return:.2f}%")
                        
                        results[strategy_id] = {
                            'success': True,
                            'strategy_return': strategy_return,
                            'buyhold_return': buyhold_return,
                            'outperforms': strategy_return > buyhold_return,
                            'trades': summary.get('total_trades', 0)
                        }
                    else:
                        print(f"  ❌ Buy & Hold比較データがありません")
                        results[strategy_id] = {'success': False, 'error': 'No Buy & Hold data'}
                else:
                    print(f"  ❌ {strategy_name} - バックテスト失敗")
                    results[strategy_id] = {'success': False, 'error': 'Backtest failed'}
                    
            except Exception as e:
                print(f"  ❌ {strategy_name} - エラー: {e}")
                results[strategy_id] = {'success': False, 'error': str(e)}
        
        # 総合結果サマリー
        print(f"\n📊 総合結果サマリー")
        print(f"=" * 50)
        
        successful_strategies = [k for k, v in results.items() if v.get('success', False)]
        print(f"✅ 成功した戦略数: {len(successful_strategies)}/{len(results)}")
        
        outperforming_strategies = [k for k, v in results.items() if v.get('outperforms', False)]
        print(f"🏆 Buy&Holdを上回った戦略: {len(outperforming_strategies)}")
        
        for strategy_id in outperforming_strategies:
            strategy_name = next(s['name'] for s in available_strategies if s['id'] == strategy_id)
            diff = results[strategy_id]['strategy_return'] - results[strategy_id]['buyhold_return']
            print(f"  - {strategy_name}: +{diff:.2f}%")
        
        active_strategies = [k for k, v in results.items() if v.get('trades', 0) > 0]
        print(f"📈 取引を実行した戦略: {len(active_strategies)}")
        
        for strategy_id in active_strategies:
            strategy_name = next(s['name'] for s in available_strategies if s['id'] == strategy_id)
            trades = results[strategy_id]['trades']
            print(f"  - {strategy_name}: {trades}回")
            
    except Exception as e:
        print(f"❌ エラー発生: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_all_strategies() 