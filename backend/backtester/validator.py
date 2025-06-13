"""
バックテスト検証・警告モジュール

バックテスト結果の妥当性をチェックし、潜在的な問題を警告する
"""

import numpy as np
from typing import Dict, Any, List, Tuple


class BacktestValidator:
    """バックテスト結果の検証クラス"""
    
    def __init__(self):
        """初期化"""
        # 警告閾値
        self.thresholds = {
            'min_sharpe_ratio': 0.5,      # 最低限のシャープレシオ
            'max_drawdown_limit': 30,      # 最大ドローダウン30%
            'min_trades': 30,              # 最小取引数
            'max_win_rate': 80,            # 勝率が高すぎる（過剰適合の疑い）
            'min_win_rate': 30,            # 勝率が低すぎる
            'max_consecutive_losses': 10    # 最大連続損失
        }
    
    def validate_results(self, backtest_result: Dict[str, Any], 
                        benchmark_result: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        バックテスト結果を検証
        
        Args:
            backtest_result: バックテスト結果
            benchmark_result: ベンチマーク結果
        
        Returns:
            警告メッセージのリスト
        """
        warnings = {
            'critical': [],    # 重大な問題
            'warning': [],     # 警告
            'info': []         # 情報
        }
        
        summary = backtest_result.get('summary', {})
        
        # 1. シャープレシオチェック
        sharpe = summary.get('sharpe_ratio', 0)
        if sharpe < self.thresholds['min_sharpe_ratio']:
            warnings['critical'].append(
                f"⚠️ シャープレシオが低すぎます ({sharpe:.2f})。"
                f"リスクに対するリターンが不十分です。"
            )
        
        # 2. 最大ドローダウンチェック
        max_dd = summary.get('max_drawdown_pct', 0)
        if max_dd > self.thresholds['max_drawdown_limit']:
            warnings['critical'].append(
                f"💀 最大ドローダウンが{max_dd:.1f}%と大きすぎます！"
                f"精神的に耐えられるか真剣に考えてください。"
            )
        
        # 3. 取引数チェック
        total_trades = summary.get('total_trades', 0)
        if total_trades < self.thresholds['min_trades']:
            warnings['warning'].append(
                f"📊 取引数が{total_trades}回と少なすぎます。"
                f"統計的に信頼できる結果ではない可能性があります。"
            )
        
        # 4. 勝率チェック（過剰適合の疑い）
        win_rate = summary.get('win_rate', 0)
        if win_rate > self.thresholds['max_win_rate']:
            warnings['critical'].append(
                f"🎯 勝率{win_rate:.1f}%は高すぎます！"
                f"過剰適合（カーブフィッティング）の可能性大です。"
            )
        elif win_rate < self.thresholds['min_win_rate']:
            warnings['warning'].append(
                f"📉 勝率{win_rate:.1f}%は低すぎます。"
                f"戦略の見直しが必要かもしれません。"
            )
        
        # 5. Buy & Holdとの比較
        if benchmark_result:
            return_diff = (summary.get('total_return_pct', 0) - 
                          benchmark_result.get('total_return_pct', 0))
            
            if return_diff < 0:
                warnings['critical'].append(
                    f"❌ Buy & Hold戦略に負けています！"
                    f"（差: {return_diff:.1f}%）"
                    f"複雑な戦略の意味がありません。"
                )
            
            # シャープレシオ比較
            sharpe_diff = (summary.get('sharpe_ratio', 0) - 
                          benchmark_result.get('sharpe_ratio', 0))
            
            if sharpe_diff < -0.1:
                warnings['warning'].append(
                    f"📊 リスク調整後リターンがBuy & Holdより劣っています。"
                    f"（シャープレシオ差: {sharpe_diff:.2f}）"
                )
        
        # 6. 手数料の影響チェック
        total_fees = summary.get('total_fees', 0)
        total_return = summary.get('total_return', 0)
        if total_return > 0 and total_fees / total_return > 0.3:
            warnings['warning'].append(
                f"💸 手数料が利益の{(total_fees/total_return)*100:.1f}%を占めています。"
                f"取引頻度を見直すべきかもしれません。"
            )
        
        # 7. 連続損失チェック
        if 'trades' in backtest_result:
            max_consecutive = self._check_consecutive_losses(backtest_result['trades'])
            if max_consecutive > self.thresholds['max_consecutive_losses']:
                warnings['warning'].append(
                    f"📉 最大{max_consecutive}連敗を記録しています。"
                    f"メンタル的に耐えられますか？"
                )
        
        return warnings
    
    def _check_consecutive_losses(self, trades: List[Dict[str, Any]]) -> int:
        """最大連続損失数をチェック"""
        max_consecutive = 0
        current_consecutive = 0
        
        for trade in trades:
            if trade.get('type') == 'EXIT' and trade.get('pnl', 0) < 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            elif trade.get('type') == 'EXIT' and trade.get('pnl', 0) > 0:
                current_consecutive = 0
        
        return max_consecutive
    
    def generate_recommendations(self, warnings: Dict[str, List[str]]) -> List[str]:
        """
        警告に基づいて改善提案を生成
        
        Args:
            warnings: 警告メッセージ
        
        Returns:
            改善提案のリスト
        """
        recommendations = []
        
        # 重大な警告がある場合
        if warnings['critical']:
            recommendations.append(
                "🚨 **この戦略は実運用に適していません！**"
            )
            recommendations.append(
                "以下の改善を検討してください："
            )
            
            # 具体的な改善案
            for warning in warnings['critical']:
                if "シャープレシオ" in warning:
                    recommendations.append(
                        "- リスク管理パラメータを調整する"
                    )
                elif "ドローダウン" in warning:
                    recommendations.append(
                        "- ポジションサイズを小さくする"
                    )
                    recommendations.append(
                        "- ストップロスを厳格に設定する"
                    )
                elif "Buy & Hold" in warning:
                    recommendations.append(
                        "- より単純な戦略を検討する"
                    )
                    recommendations.append(
                        "- 取引頻度を減らす"
                    )
                elif "勝率" in warning and "高すぎ" in warning:
                    recommendations.append(
                        "- パラメータ数を減らす"
                    )
                    recommendations.append(
                        "- より長期間でバックテストする"
                    )
                    recommendations.append(
                        "- アウトオブサンプルテストを実施する"
                    )
        
        return recommendations
