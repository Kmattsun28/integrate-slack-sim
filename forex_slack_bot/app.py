import sys
import os
# Ensure llm_forex_slack_simulator is importable
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
"""
メインアプリケーション - Slackイベントハンドラとルーティング
"""

import os
import asyncio
import logging
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

from config import Config
from handlers.inference_handler import InferenceHandler, setup_inference_handlers
from handlers.deal_handler import DealHandler, setup_deal_handlers
from handlers.balance_handler import BalanceHandler, setup_balance_handlers
from handlers.common_handlers import CommonHandlers, setup_common_handlers
from schedulers.periodic_inference import PeriodicInference
from utils.error_handler import ErrorHandler

# 環境変数のロード
load_dotenv()

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ForexSlackBot:
    def __init__(self):
        """Forex Slack Botの初期化"""
        self.app = App(token=Config.SLACK_BOT_TOKEN)
        self.scheduler = BackgroundScheduler()
        
        # ハンドラの初期化
        self.inference_handler = InferenceHandler()
        self.deal_handler = DealHandler()
        self.balance_handler = BalanceHandler()
        self.common_handlers = CommonHandlers()
        self.periodic_inference = PeriodicInference()
        
        # エラーハンドラの設定
        self.error_handler = ErrorHandler()
        
        self._register_handlers()
        self._setup_scheduler()

    def _register_handlers(self):
        """イベントハンドラの登録"""
        setup_inference_handlers(self.app)
        setup_deal_handlers(self.app, self.deal_handler, self.error_handler)
        setup_balance_handlers(self.app, self.balance_handler, self.error_handler)
        setup_common_handlers(self.app, self.common_handlers, self.error_handler)

    def _setup_scheduler(self):
        """定期実行処理のスケジューリング設定"""
        if Config.PERIODIC_INFERENCE_ENABLED:
            self.scheduler.add_job(
                func=self.periodic_inference.run_periodic_inference,
                trigger="interval",
                hours=Config.PERIODIC_INFERENCE_INTERVAL_HOURS,
                id='periodic_inference'
            )
            logger.info(f"定期推論を{Config.PERIODIC_INFERENCE_INTERVAL_HOURS}時間間隔で設定しました")

    def start(self):
        """Slack Botの開始"""
        logger.info("Slack Botを開始します...")
        if Config.PERIODIC_INFERENCE_ENABLED:
            self.scheduler.start()
            logger.info("定期実行スケジューラーを開始しました")
        handler = SocketModeHandler(self.app, Config.SLACK_APP_TOKEN)
        handler.start()

    def stop(self):
        """Slack Botの停止"""
        logger.info("Slack Botを停止します...")
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("定期実行スケジューラーを停止しました")

if __name__ == "__main__":
    bot = ForexSlackBot()
    try:
        bot.start()
    except KeyboardInterrupt:
        logger.info("キーボード割り込みを受信しました")
        bot.stop()
    except Exception as e:
        logger.error(f"予期しないエラーが発生しました: {e}")
        bot.stop()