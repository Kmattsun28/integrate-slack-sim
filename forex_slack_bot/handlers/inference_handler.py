# forex_slack_bot/handlers/inference_handler.py

import logging
from datetime import datetime
from config import Config
import subprocess  # ◀◀◀ subprocess をインポート
import os          # ◀◀◀ os をインポート

from services.inference_service import InferenceService
from services.trading_service import TradingService
from utils.slack_utils import SlackUtils

logger = logging.getLogger(__name__)

class InferenceHandler:
    """推論コマンドのハンドラクラス（実取引データ専用）"""

    def __init__(self):
        self.inference_service = InferenceService()
        self.trading_service = TradingService()
        self.slack_utils = SlackUtils()

    def handle_inference(self, respond, command):
        """
        /inference コマンドの処理
        - inference.py をサブプロセスとして実行し、GPUメモリを確実に解放します。
        """
        user_id = command.get("user_id")
        channel_id = command.get("channel_id")
        logger.info(f"handle_inference called by user {user_id} in channel {channel_id}")

        try:
            # 推論が実行中かどうかのチェック (既存のロジックを流用)
            with self.inference_service._inference_lock:
                if self.inference_service._inference_running:
                    respond({
                        "text": "🔄 すでに推論が実行中です。完了までお待ちください。",
                        "response_type": "ephemeral"
                    })
                    return
                self.inference_service._inference_running = True

            # ユーザーへの即時応答
            respond({
                "text": "🚀 推論を開始しました。完了まで数分かかることがあります...",
                "response_type": "in_channel"
            })

            # --- ここからがサブプロセス呼び出しの核心部分 ---
            
            # inference.pyへのパスを構築
            # このファイルの場所からプロジェクトルートを基準にパスを解決
            inference_script_path = os.path.abspath(os.path.join(
                os.path.dirname(__file__), '..', '..', 'inference.py'
            ))

            # 出力ディレクトリを生成
            base_dir = Config.REAL_DATA_OUTPUT_DIR
            now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(base_dir, now_str)
            os.makedirs(output_dir, exist_ok=True)

            # サブプロセスで実行するコマンドを構築
            command_to_run = [
                "python",
                inference_script_path,
                "--transaction_file", Config.TRANSACTION_LOG_FILE,
                "--output_dir", output_dir
            ]

            logger.info(f"Executing subprocess: {' '.join(command_to_run)}")

            # サブプロセスを実行
            # `run` は完了まで待機するため、非同期処理を待つ必要はない
            result = subprocess.run(
                command_to_run,
                capture_output=True,
                text=True,
                encoding='utf-8', # 文字化け対策
                timeout=600  # タイムアウトを10分に設定
            )

            # --- 実行結果のハンドリング ---

            if result.returncode == 0:
                # 成功した場合
                logger.info(f"Inference script stdout:\n{result.stdout}")
                
                # response.txtから結果を読み込む
                response_file = os.path.join(output_dir, "response.txt")
                if os.path.exists(response_file):
                    with open(response_file, 'r', encoding='utf-8') as f:
                        inference_output = f.read()
                    
                    # Slackに結果を通知
                    respond({
                        "text": f"✅ 推論が完了しました。\n\n**抽出された取引指示:**\n```{inference_output}```",
                        "response_type": "in_channel"
                    })
                else:
                    respond({
                        "text": f"✅ 推論プロセスは正常に終了しましたが、結果ファイルが見つかりませんでした。",
                        "response_type": "in_channel"
                    })
            else:
                # 失敗した場合
                error_message = f"❌ 推論の実行に失敗しました。\n\n**エラーログ:**\n```{result.stderr}```"
                logger.error(f"Inference script stderr:\n{result.stderr}")
                respond({
                    "text": error_message,
                    "response_type": "in_channel"  # エラーもチャンネルに通知
                })

        except subprocess.TimeoutExpired:
            logger.error("Inference process timed out.")
            respond({
                "text": "❌ 推論プロセスがタイムアウトしました（10分）。処理を中断します。",
                "response_type": "in_channel"
            })
        except Exception as e:
            logger.error(f"handle_inferenceで予期せぬ例外: {e}", exc_info=True)
            respond({
                "text": f"❌ ハンドラで予期せぬエラーが発生しました: {str(e)}",
                "response_type": "ephemeral"
            })
        finally:
            # 必ずロックを解放する
            with self.inference_service._inference_lock:
                self.inference_service._inference_running = False

# ... ファイルの残りの部分は変更不要 ...

def setup_inference_handlers(app):
    """
    推論関連のハンドラを設定
    """
    inference_handler = InferenceHandler()
    logger.info("setup_inference_handlers: /inference コマンドハンドラ登録開始")
    
    @app.command("/inference")
    def handle_inference_command(ack, respond, command):
        logger.info(f"/inferenceコマンド受信: command={command}")
        ack()  # まずSlackに3秒以内にACKを返す
        
        # handle_inference は同期的にサブプロセスを呼び出し、完了を待つ
        inference_handler.handle_inference(respond, command)

    logger.info("実取引推論ハンドラが設定されました (/inference)")