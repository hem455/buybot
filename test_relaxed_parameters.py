#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
sys.path.append('.')
from backend.backtester import Backtester
from datetime import datetime, timedelta

def test_relaxed_parameters():
    """MA CrossとMACD+RSI戦略のパラメータを緩和してテスト"""
    print("🔧 パラメータ緩和テスト開始")
    
    try:
        backtester = Backtester()
        
        # テスト期間設定（少し長めに）
        end_date = datetime.now() - timedelta(days=1)
        start_date = end_date - timedelta(days=14)  # 2週間
        
        print(f"📅 テスト期間: {start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}")
        
        # 1. MA Cross戦略 - パラメータ緩和
        print("\n" + "="*60)
        print("🚀 MA Cross戦略 - パラメータ緩和テスト")
        print("="*60)
        
        # 元のパラメータ
        original_params = {'short_period': 5, 'long_period': 20, 'confirmation_bars': 1}
        print(f"📊 元のパラメータ: {original_params}")
        
        result = backtester.run_backtest(
            symbol='BTC_JPY',
            interval='15min',
            strategy_id='ma_cross',
            start_date=start_date,
            end_date=end_date,
            parameters=original_params
        )
        print(f"  取引数: {result['summary']['total_trades']}回")
        print(f"  収益率: {result['summary']['total_return_pct']:.2f}%")
        
        # 緩和パラメータ1: 短期間の移動平均
        relaxed_params1 = {'short_period': 3, 'long_period': 10, 'confirmation_bars': 1}
        print(f"\n📊 緩和パラメータ1: {relaxed_params1}")
        
        result1 = backtester.run_backtest(
            symbol='BTC_JPY',
            interval='15min',
            strategy_id='ma_cross',
            start_date=start_date,
            end_date=end_date,
            parameters=relaxed_params1
        )
        print(f"  取引数: {result1['summary']['total_trades']}回")
        print(f"  収益率: {result1['summary']['total_return_pct']:.2f}%")
        
        # 緩和パラメータ2: さらに短期間
        relaxed_params2 = {'short_period': 2, 'long_period': 7, 'confirmation_bars': 0}
        print(f"\n📊 緩和パラメータ2: {relaxed_params2}")
        
        result2 = backtester.run_backtest(
            symbol='BTC_JPY',
            interval='15min',
            strategy_id='ma_cross',
            start_date=start_date,
            end_date=end_date,
            parameters=relaxed_params2
        )
        print(f"  取引数: {result2['summary']['total_trades']}回")
        print(f"  収益率: {result2['summary']['total_return_pct']:.2f}%")
        
        # 2. MACD+RSI戦略 - パラメータ緩和
        print("\n" + "="*60)
        print("🚀 MACD+RSI戦略 - パラメータ緩和テスト")
        print("="*60)
        
        # 元のパラメータ
        original_rsi_params = {'rsi_oversold': 30, 'rsi_overbought': 70, 'macd_threshold': 0}
        print(f"📊 元のパラメータ: {original_rsi_params}")
        
        result = backtester.run_backtest(
            symbol='BTC_JPY',
            interval='15min',
            strategy_id='macd_rsi',
            start_date=start_date,
            end_date=end_date,
            parameters=original_rsi_params
        )
        print(f"  取引数: {result['summary']['total_trades']}回")
        print(f"  収益率: {result['summary']['total_return_pct']:.2f}%")
        
        # 緩和パラメータ1: RSI閾値を緩和
        relaxed_rsi_params1 = {'rsi_oversold': 40, 'rsi_overbought': 60, 'macd_threshold': 0}
        print(f"\n📊 緩和パラメータ1: {relaxed_rsi_params1}")
        
        result1 = backtester.run_backtest(
            symbol='BTC_JPY',
            interval='15min',
            strategy_id='macd_rsi',
            start_date=start_date,
            end_date=end_date,
            parameters=relaxed_rsi_params1
        )
        print(f"  取引数: {result1['summary']['total_trades']}回")
        print(f"  収益率: {result1['summary']['total_return_pct']:.2f}%")
        
        # 緩和パラメータ2: さらに緩和
        relaxed_rsi_params2 = {'rsi_oversold': 45, 'rsi_overbought': 55, 'macd_threshold': -0.1}
        print(f"\n📊 緩和パラメータ2: {relaxed_rsi_params2}")
        
        result2 = backtester.run_backtest(
            symbol='BTC_JPY',
            interval='15min',
            strategy_id='macd_rsi',
            start_date=start_date,
            end_date=end_date,
            parameters=relaxed_rsi_params2
        )
        print(f"  取引数: {result2['summary']['total_trades']}回")
        print(f"  収益率: {result2['summary']['total_return_pct']:.2f}%")
        
        print("\n" + "="*60)
        print("📋 パラメータ緩和テスト結果サマリー")
        print("="*60)
        print("🎯 MA Cross戦略:")
        print(f"  元設定(5,20): {result['summary']['total_trades']}回取引")
        print(f"  緩和1(3,10): {result1['summary']['total_trades']}回取引")
        print(f"  緩和2(2,7): {result2['summary']['total_trades']}回取引")
        
        print("\n🎯 MACD+RSI戦略:")
        print(f"  元設定(30/70): {result['summary']['total_trades']}回取引")
        print(f"  緩和1(40/60): {result1['summary']['total_trades']}回取引")
        print(f"  緩和2(45/55): {result2['summary']['total_trades']}回取引")
        
    except Exception as e:
        print(f"❌ エラー発生: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_relaxed_parameters() 