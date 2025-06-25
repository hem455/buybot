"""
総資産自動保存スケジューラー

毎日指定時刻に総資産データをデータベースに自動保存します。
"""

import schedule
import time
import sys
from pathlib import Path
from datetime import datetime
import threading

# プロジェクトルートを堅牢な方法でパスに追加
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from backend.gmo_client import GMOCoinClient
from backend.logger import get_logger


class AssetScheduler:
    """総資産自動保存スケジューラー"""
    
    def __init__(self, save_time: str = "23:55"):
        """
        初期化
        
        Args:
            save_time: 保存時刻（HH:MM形式）
        """
        self.save_time = save_time
        self.logger = get_logger()
        self.is_running = False
        self.scheduler_thread = None
        self.scheduled_job = None  # 特定ジョブの参照を保存
        
        try:
            self.gmo_client = GMOCoinClient()
            self.logger.info("GMOクライアント初期化完了")
        except Exception as e:
            self.logger.error(f"GMOクライアント初期化失敗: {e}")
            self.gmo_client = None
    
    def save_daily_assets_job(self):
        """日次総資産保存ジョブ"""
        try:
            if not self.gmo_client:
                self.logger.error("GMOクライアントが利用できません")
                return
            
            self.logger.info("=== 日次総資産保存ジョブ開始 ===")
            
            # 総資産データを保存
            success = self.gmo_client.save_daily_assets("自動保存")
            
            if success:
                self.logger.info("✅ 日次総資産保存完了")
                
                # 今日の統計情報も取得してログ出力
                asset_data = self.gmo_client.calculate_total_assets()
                if 'error' not in asset_data:
                    self.logger.info(f"📊 今日の総資産: ¥{asset_data['total_assets']:,.0f}")
                    self.logger.info(f"   - JPY残高: ¥{asset_data['jpy_balance']:,.0f}")
                    self.logger.info(f"   - 現物評価額: ¥{asset_data['spot_value']:,.0f}")
                    self.logger.info(f"   - 証拠金損益: ¥{asset_data['margin_pnl']:,.0f}")
            else:
                self.logger.error("❌ 日次総資産保存失敗")
            
            self.logger.info("=== 日次総資産保存ジョブ終了 ===")
            
        except Exception as e:
            self.logger.error(f"日次総資産保存ジョブエラー: {e}")
    
    def start_scheduler(self):
        """スケジューラーを開始"""
        if self.is_running:
            self.logger.warning("スケジューラーは既に実行中です")
            return
        
        # 毎日の指定時刻にジョブを設定（ジョブ参照を保存）
        self.scheduled_job = schedule.every().day.at(self.save_time).do(self.save_daily_assets_job)
        
        self.logger.info(f"📅 スケジューラー開始: 毎日 {self.save_time} に総資産を自動保存")
        
        # バックグラウンドでスケジューラーを実行（daemon=True除去でgraceful shutdown対応）
        self.is_running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, name="AssetScheduler")
        self.scheduler_thread.start()
    
    def _run_scheduler(self):
        """スケジューラーの実行ループ"""
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # 1分ごとにチェック
            except Exception as e:
                self.logger.error(f"スケジューラー実行エラー: {e}")
                time.sleep(60)
    
    def stop_scheduler(self, timeout: int = 30):
        """
        スケジューラーを graceful に停止
        
        Args:
            timeout: スレッド終了待機のタイムアウト（秒）
        """
        if not self.is_running:
            self.logger.warning("スケジューラーは既に停止しています")
            return
        
        self.logger.info("📅 スケジューラー停止開始...")
        
        # 実行フラグを停止に設定
        self.is_running = False
        
        # 特定のジョブのみキャンセル（他のスケジューラーに影響なし）
        if self.scheduled_job:
            schedule.cancel_job(self.scheduled_job)
            self.scheduled_job = None
            self.logger.info("🗑️ スケジュールされたジョブをキャンセル")
        
        # スレッドの graceful shutdown
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.logger.info(f"⏳ スレッド終了を待機中（タイムアウト: {timeout}秒）...")
            self.scheduler_thread.join(timeout=timeout)
            
            if self.scheduler_thread.is_alive():
                self.logger.warning("⚠️ スレッドがタイムアウト内に終了しませんでした")
            else:
                self.logger.info("✅ スレッドが正常に終了しました")
        
        self.logger.info("📅 スケジューラー停止完了")
    
    def get_next_run_time(self):
        """次回実行時刻を取得"""
        jobs = schedule.get_jobs()
        if jobs:
            return jobs[0].next_run
        return None
    
    def manual_save(self):
        """手動で総資産を保存"""
        self.logger.info("🖱️ 手動総資産保存実行")
        self.save_daily_assets_job()


def main():
    """メイン関数（スタンドアロン実行時）"""
    print("🚀 総資産自動保存スケジューラー開始")
    
    scheduler = AssetScheduler(save_time="23:55")  # 毎日23:55に保存
    
    try:
        scheduler.start_scheduler()
        
        print(f"⏰ 次回実行予定: {scheduler.get_next_run_time()}")
        print("📝 Ctrl+C で停止")
        
        # メインスレッドを維持
        while True:
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\n🛑 スケジューラーを停止中...")
        scheduler.stop_scheduler(timeout=10)  # 10秒でタイムアウト
        print("✅ 停止完了")


if __name__ == "__main__":
    main() 