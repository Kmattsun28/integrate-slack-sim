#!/usr/bin/env python3
"""
定期実行専用スクリプト - Docker Compose用
"""

import os
import sys
import asyncio
import logging
import signal
from datetime import datetime
from pathlib import Path

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config import Config
from services.inference_service import InferenceService
from models.balance_manager import BalanceManager
from utils.slack_utils import SlackUtils

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/logs/scheduler.log')
    ]
)
logger = logging.getLogger(__name__)

class SchedulerService:
    """定期実行スケジューラーサービス"""
    
    def __init__(self):
        self.inference_service = InferenceService()
        self.balance_manager = BalanceManager()
        self.slack_utils = SlackUtils()
        self.running = True
        
        # シグナルハンドラーの設定
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """シグナルハンドラー"""
        logger.info(f"シグナル {signum} を受信しました。停止処理を開始します...")
        self.running = False
    
    async def run_periodic_inference(self):
        """定期推論を実行（設定により実データまたはシミュレーション）"""
        try:
            use_real_data = Config.PERIODIC_INFERENCE_USE_REAL_DATA
            data_type = "実データ" if use_real_data else "シミュレーション"
            logger.info(f"定期推論を開始します（{data_type}使用）")

            # シミュレーションの定期実行を一時停止
            if not use_real_data:
                logger.info("シミュレーションの定期実行は一時停止中です（run_periodic_inferenceはスキップされました）")
                return

            # 現在の残高を取得
            current_balance = self.balance_manager.get_balance()
            logger.info(f"現在の残高: {current_balance}")

            # 推論実行（実データオプション付き）
            if use_real_data:
                inference_result = await self.inference_service.run_inference_with_real_data(current_balance, True)
            else:
                inference_result = await self.inference_service.run_inference(current_balance)
            
            # 結果をSlackに通知
            await self._send_inference_result(inference_result, use_real_data)
            
            logger.info(f"定期推論が正常に完了しました（{data_type}使用）")
            
        except Exception as e:
            logger.error(f"定期推論実行中にエラー: {e}")
            await self._send_error_notification(str(e))
    
    async def _send_inference_result(self, result, use_real_data=False):
        """推論結果をSlackに送信（実データ対応版）"""
        try:
            channel = Config.DEFAULT_CHANNEL
            data_type = "実データ" if use_real_data else "シミュレーション"
            data_source = result.get("data_source", "simulation")
            
            # 基本メッセージ
            message = f"🤖 **定期推論結果**（{data_type}使用）\n"
            message += f"📋 データソース: {data_source}\n\n"
            message += f"📊 **市場分析**\n{result.get('market_analysis', 'N/A')}\n\n"
            
            # 推奨取引
            recommended_trades = result.get('recommended_trades', [])
            if recommended_trades:
                message += "💡 **推奨取引**\n"
                for trade in recommended_trades:
                    action_emoji = "📈" if trade['action'] == 'buy' else "📉"
                    confidence = trade.get('confidence', 0) * 100
                    message += f"{action_emoji} {trade['pair']}: {trade['action']} "
                    message += f"({confidence:.0f}%信頼度)\n"
                    if trade.get('reasoning'):
                        message += f"   理由: {trade['reasoning']}\n"
                message += "\n"
            else:
                message += "💡 **推奨取引**: 現時点では新しい取引を推奨しません\n\n"
            
            # リスク評価
            message += f"⚠️ **リスク評価**\n{result.get('risk_assessment', 'N/A')}\n\n"
            
            # 実データ特有の情報
            if use_real_data and result.get('trades_performed'):
                message += f"📊 **実行済み取引数**: {len(result['trades_performed'])}件\n\n"
            
            # 全体的な信頼度
            confidence = result.get("confidence_score", 0) * 100
            message += f"🎯 **推論信頼度**: {confidence:.0f}%\n"
            message += f"🕐 **実行時刻**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            await self.slack_utils.send_message(channel, message)
            
        except Exception as e:
            logger.error(f"Slack通知送信エラー: {e}")
    
    async def _send_error_notification(self, error_message):
        """エラー通知をSlackに送信"""
        try:
            channel = Config.ADMIN_CHANNEL
            message = f"❌ **定期推論エラー**\n\n"
            message += f"エラー内容: {error_message}\n"
            message += f"発生時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            await self.slack_utils.send_message(channel, message)
            
        except Exception as e:
            logger.error(f"エラー通知送信エラー: {e}")
    
    async def start(self):
        """スケジューラーサービスを開始"""
        logger.info("定期実行スケジューラーを開始します...")
        
        interval_seconds = Config.PERIODIC_INFERENCE_INTERVAL_HOURS * 3600
        logger.info(f"実行間隔: {Config.PERIODIC_INFERENCE_INTERVAL_HOURS}時間")
        
        while self.running:
            try:
                # 定期推論を実行
                await self.run_periodic_inference()
                
                # 次回実行まで待機
                logger.info(f"次回実行まで{Config.PERIODIC_INFERENCE_INTERVAL_HOURS}時間待機します...")
                for _ in range(interval_seconds):
                    if not self.running:
                        break
                    await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"スケジューラーループでエラー: {e}")
                # エラーが発生した場合、5分後にリトライ
                await asyncio.sleep(300)
        
        logger.info("定期実行スケジューラーを停止しました")

async def main():
    """メイン関数"""
    # データディレクトリとログディレクトリを作成
    os.makedirs('/app/data', exist_ok=True)
    os.makedirs('/app/logs', exist_ok=True)
    
    scheduler = SchedulerService()
    
    try:
        await scheduler.start()
    except KeyboardInterrupt:
        logger.info("キーボード割り込みを受信しました")
    except Exception as e:
        logger.error(f"予期しないエラー: {e}")

if __name__ == "__main__":
    asyncio.run(main())
