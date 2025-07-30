# forex_slack_bot/schedulers/periodic_inference.py

import logging
import subprocess # ◀◀◀ インポート
import os         # ◀◀◀ インポート
from datetime import datetime
from config import Config
from utils.slack_utils import SlackUtils

logger = logging.getLogger(__name__)

class PeriodicInference:
    
    def __init__(self):
        # InferenceServiceやTradingServiceへの依存を減らし、シンプルにする
        self.slack_utils = SlackUtils()
        # ロックファイルなど、簡易的な重複実行防止機構を導入しても良い
        
    def run_periodic_inference(self):
        """
        定期推論を実行（inference.pyをサブプロセスで呼び出す）
        """
        logger.info("定期推論の実行を開始します...")

        try:
            # inference.pyへのパスを構築
            inference_script_path = os.path.abspath(os.path.join(
                os.path.dirname(__file__), '..', '..', 'inference.py'
            ))

            # 出力ディレクトリを生成
            base_dir = Config.REAL_DATA_OUTPUT_DIR
            now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(base_dir, now_str)
            os.makedirs(output_dir, exist_ok=True)
            
            # コマンドを構築
            command_to_run = [
                "python",
                inference_script_path,
                "--transaction_file", Config.TRANSACTION_LOG_FILE,
                "--output_dir", output_dir
            ]
            
            logger.info(f"Executing periodic inference: {' '.join(command_to_run)}")
            
            # サブプロセスを実行
            result = subprocess.run(
                command_to_run,
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=600
            )

            if result.returncode == 0:
                logger.info("定期推論が正常に完了しました。")
                response_file = os.path.join(output_dir, "response.txt")
                if os.path.exists(response_file):
                    with open(response_file, 'r', encoding='utf-8') as f:
                        inference_output = f.read()
                    
                    # Slackに通知
                    self.slack_utils.client.chat_postMessage(
                        channel=Config.DEFAULT_CHANNEL,
                        text=f"🤖 **定期推論が完了しました**\n\n**抽出された取引指示:**\n```{inference_output}```"
                    )
            else:
                logger.error(f"定期推論でエラーが発生しました。\n{result.stderr}")
                # Slackにエラー通知
                self.slack_utils.client.chat_postMessage(
                    channel=Config.ADMIN_CHANNEL, # エラーは管理者チャンネルへ
                    text=f"❌ **定期推論でエラー**\n\n```{result.stderr}```"
                )

        except Exception as e:
            logger.error(f"定期推論のスケジューラ自体でエラー: {e}", exc_info=True)
            self.slack_utils.client.chat_postMessage(
                channel=Config.ADMIN_CHANNEL,
                text=f"❌ 定期推論のスケジューラ自体でエラーが発生しました。\n```{e}```"
            )