"""
推論ハンドラ - !inference コマンド処理（実取引データ専用）
"""

import logging
from datetime import datetime
from config import Config

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
        !inference コマンドの処理
        - 実際の取引データを使用した推論のみ実行
        - 非同期で推論を実行
        - 即座に開始メッセージを返し、完了次第、結果をお知らせします。
        - 推論中の重複実行防止
        - エラーハンドリング
        """
        user_id = command.get("user_id")
        channel_id = command.get("channel_id")
        command_text = command.get("text", "").strip()
        logger.info(f"handle_inference called: user_id={user_id}, channel_id={channel_id}, text={command_text}")
        try:
            # 推論が既に実行中かどうかをatomicに判定・セット
            with self.inference_service._inference_lock:
                if self.inference_service._inference_running:
                    respond({
                        "text": "🔄 すでに推論が実行中です。完了までお待ちください。",
                        "response_type": "ephemeral"
                    })
                    return
                self.inference_service._inference_running = True
            # 開始メッセージ
            respond({
                "text": "🚀 推論を開始しました。完了次第、結果をお知らせします。",
                "response_type": "in_channel"
            })
            # llm_real_transaction/inference.pyのrun_inferenceを呼び出す
            import importlib.util
            import datetime as dt
            import os
            spec = importlib.util.spec_from_file_location("inference", os.path.join(os.path.dirname(os.path.dirname(__file__)), "../inference.py"))
            inference_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(inference_module)
            # 残高取得
            current_balance = self.trading_service.get_current_balance()
            start_time = dt.datetime.utcnow()
            transaction_file = Config.TRANSACTION_LOG_FILE
            # --- 保存先ディレクトリを {日付時刻} サブディレクトリ付きに統一 ---
            base_dir = Config.REAL_DATA_OUTPUT_DIR
            now_str = start_time.strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(base_dir, now_str)
            os.makedirs(output_dir, exist_ok=True)
            result = inference_module.run_inference(start=start_time, current_assets=current_balance, transaction_file=transaction_file, output_dir=output_dir)
            # 結果をSlack通知（簡易）
            respond({
                "text": f"✅ 推論が完了しました。結果: {result}",
                "response_type": "in_channel"
            })
        except Exception as e:
            logger.error(f"handle_inferenceで例外: {e}")
            respond({
                "text": f"❌ 推論コマンド実行時にエラーが発生しました: {str(e)}",
                "response_type": "ephemeral"
            })
        finally:
            with self.inference_service._inference_lock:
                self.inference_service._inference_running = False

    async def handle_inference_async(self, respond, command):
        """
        /inference コマンドの非同期処理（inference.pyをサブプロセスで実行し、終了後にGPUメモリ解放）
        """
        import asyncio
        import subprocess
        import os
        import glob
        from datetime import datetime
        user_id = command.get("user_id")
        channel_id = command.get("channel_id")
        command_text = command.get("text", "").strip()
        logger.info(f"handle_inference_async called: user_id={user_id}, channel_id={channel_id}, text={command_text}")
        try:
            if self.inference_service.is_inference_running():
                await respond({
                    "text": "🔄 すでに推論が実行中です。完了までお待ちください。",
                    "response_type": "ephemeral"
                })
                return
            await respond({
                "text": "🚀 推論を開始しました。完了次第、結果をお知らせします。",
                "response_type": "in_channel"
            })
            # inference.pyをサブプロセスで実行
            proc = await asyncio.create_subprocess_exec(
                "python3", os.path.join(os.path.dirname(os.path.dirname(__file__)), "inference.py"),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            logger.info(f"inference.py stdout: {stdout.decode()}")
            logger.info(f"inference.py stderr: {stderr.decode()}")
            # 実行後、real_outディレクトリの最新ファイルを取得してSlack通知
            real_out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "real_out")
            list_dirs = sorted([d for d in os.listdir(real_out_dir) if os.path.isdir(os.path.join(real_out_dir, d))], reverse=True)
            if list_dirs:
                latest_dir = os.path.join(real_out_dir, list_dirs[0])
                # 推論結果ファイル（response.txt等）を探す
                result_files = glob.glob(os.path.join(latest_dir, "*.txt"))
                if result_files:
                    result_file = result_files[0]
                    with open(result_file, "r", encoding="utf-8") as f:
                        result_text = f.read()
                    await respond({
                        "text": f"✅ 推論が完了しました。結果:\n{result_text}",
                        "response_type": "in_channel"
                    })
                    return
            await respond({
                "text": "✅ 推論は完了しましたが、結果ファイルが見つかりませんでした。",
                "response_type": "in_channel"
            })
        except Exception as e:
            logger.error(f"handle_inference_asyncで例外: {e}")
            await respond({
                "text": f"❌ 推論コマンド実行時にエラーが発生しました: {str(e)}",
                "response_type": "ephemeral"
            })

    def _run_inference_sync(self, channel_id, user_id):
        """
        バックグラウンドでの実取引データ推論実行
        """
        try:
            logger.info(f"実取引データ推論を開始します。ユーザー: {user_id}, チャンネル: {channel_id}")
            
            # 現在の残高を取得
            current_balance = self.trading_service.get_current_balance()
            
            # 実取引データ推論を実行
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            inference_result = loop.run_until_complete(
                self.inference_service.run_inference(current_balance)
            )
            
            # 結果をフォーマット
            result_text = self._format_inference_result(inference_result)
            
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(result_text)
                temp_file_path = f.name
            
            filename = f"inference_result_real_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            logger.info(f"推論結果送信先チェック: channel_id={channel_id}, user_id={user_id}")
            # DMチャンネルの場合はファイル添付不可のためテキストのみ送信
            if channel_id and channel_id.startswith("D"):
                logger.info("DMチャンネルのためテキストのみ送信します")
                msg_result = loop.run_until_complete(self.slack_utils.send_message(
                    channel_id=channel_id,
                    text="✅ 実取引データ推論が完了しました！結果をご確認ください。\n\n" + result_text
                ))
                logger.info(f"send_message(DMテキスト)結果: {msg_result}")
            elif not channel_id or channel_id == "channel_not_found":
                logger.warning(f"channel_idが不正のためDM送信を試みます: user_id={user_id}")
                dm_result = loop.run_until_complete(self.slack_utils.send_dm(
                    user_id=user_id,
                    text="✅ 実取引データ推論が完了しました！結果をご確認ください。\n(チャンネルIDが不明なためDMで送信)\n\n" + result_text
                ))
                logger.info(f"send_dm(結果テキスト)結果: {dm_result}")
            else:
                # パブリックチャンネル等はファイル添付
                file_result = loop.run_until_complete(self.slack_utils.send_message_with_file(
                    channel_id=channel_id,
                    text="✅ 実取引データ推論が完了しました！結果をご確認ください。",
                    file_path=temp_file_path,
                    filename=filename
                ))
                logger.info(f"send_message_with_file結果: {file_result}")
            logger.info("実取引データ推論が正常に完了しました")
        except Exception as e:
            logger.error(f"推論実行中にエラーが発生しました: {e}")
            error_message = self._get_error_message(e)
            if channel_id and channel_id.startswith("D"):
                logger.info("DMチャンネルのためエラーメッセージもテキストのみ送信します")
                msg_result = loop.run_until_complete(self.slack_utils.send_message(
                    channel_id=channel_id,
                    text=f"❌ {error_message}"
                ))
                logger.info(f"send_message(DMエラー)結果: {msg_result}")
            elif not channel_id or channel_id == "channel_not_found":
                logger.warning(f"channel_idが不正のためDMでエラー送信を試みます: user_id={user_id}")
                dm_result = loop.run_until_complete(self.slack_utils.send_dm(
                    user_id=user_id,
                    text=f"❌ {error_message}"
                ))
                logger.info(f"send_dm(エラー)結果: {dm_result}")
            else:
                msg_result = loop.run_until_complete(self.slack_utils.send_message(
                    channel_id=channel_id,
                    text=f"❌ {error_message}"
                ))
                logger.info(f"send_message(エラー)結果: {msg_result}")
        finally:
            # 推論状態をリセット
            self.inference_service.reset_inference_state()

    def _format_inference_result(self, result: dict) -> str:
        """
        推論結果をわかりやすいテキストにフォーマット（実取引データ専用）
        """
        formatted_text = []
        
        data_source = result.get("data_source", "real_trading_data")
        
        formatted_text.append("=" * 50)
        formatted_text.append("📊 実取引データ為替推論結果")
        formatted_text.append("=" * 50)
        formatted_text.append(f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        formatted_text.append(f"データソース: {data_source}")
        formatted_text.append("")
        
        # 推奨取引があれば表示
        if result.get("recommended_trades"):
            formatted_text.append("💡 推奨取引:")
            for trade in result["recommended_trades"]:
                action = "買い" if trade.get("action") == "buy" else "売り"
                confidence = trade.get("confidence", 0) * 100
                formatted_text.append(f"  - {trade.get('pair')}: {action} {trade.get('amount')} @ {trade.get('rate')}")
                formatted_text.append(f"    信頼度: {confidence:.0f}%")
                if trade.get("reasoning"):
                    formatted_text.append(f"    理由: {trade.get('reasoning')}")
            formatted_text.append("")
        else:
            formatted_text.append("💡 推奨取引: なし（現時点では取引を控えることを推奨）")
            formatted_text.append("")
        
        # 現在の残高情報
        if result.get("current_balance"):
            formatted_text.append("💰 現在の残高:")
            for currency, amount in result["current_balance"].items():
                formatted_text.append(f"  {currency}: {amount:,.2f}")
            formatted_text.append("")
        
        # 市場分析
        if result.get("market_analysis"):
            formatted_text.append("📈 市場分析:")
            formatted_text.append(result["market_analysis"])
            formatted_text.append("")
        
        # リスク評価
        if result.get("risk_assessment"):
            formatted_text.append("⚠️ リスク評価:")
            formatted_text.append(result["risk_assessment"])
            formatted_text.append("")
        
        # 実取引データ特有の情報
        if result.get("real_data_summary"):
            formatted_text.append("🔍 実取引データ分析:")
            formatted_text.append(result["real_data_summary"])
            formatted_text.append("")
        
        # 免責事項
        formatted_text.append("=" * 50)
        formatted_text.append("⚠️  重要な注意事項")
        formatted_text.append("=" * 50)
        formatted_text.append("• この推論結果は実際の取引データに基づく分析ですが、")
        formatted_text.append("  投資助言ではありません")
        formatted_text.append("• 為替取引にはリスクが伴います")
        formatted_text.append("• 取引の判断は自己責任で行ってください")
        formatted_text.append("• 過去の実績が将来の結果を保証するものではありません")
        
        return "\n".join(formatted_text)
    
    def _get_error_message(self, error: Exception) -> str:
        """
        エラーに応じた適切なメッセージを返す
        """
        error_str = str(error).lower()
        
        if "memory" in error_str or "cuda" in error_str:
            return "GPUメモリ不足のため推論に失敗しました。しばらく時間をおいて再度お試しください。"
        elif "timeout" in error_str:
            return "推論処理がタイムアウトしました。システムが混雑している可能性があります。"
        elif "推論が既に実行中" in error_str:
            return "他の推論処理が実行中です。完了までお待ちください。"
        elif "network" in error_str or "connection" in error_str:
            return "ネットワークエラーが発生しました。接続を確認して再度お試しください。"
        elif "llm_forex_slack_simulator" in error_str:
            return "実取引推論システムの読み込みに失敗しました。システム管理者にお問い合わせください。"
        else:
            return f"推論処理中にエラーが発生しました: {str(error)[:100]}"


def setup_inference_handlers(app):
    """
    推論関連のハンドラを設定
    """
    inference_handler = InferenceHandler()
    logger.info("setup_inference_handlers: /inference コマンドハンドラ登録開始")
    @app.command("/inference")
    def handle_inference_command(ack, respond, command):
        logger.info(f"/inferenceコマンド受信: command={command}")
        ack()
        inference_handler.handle_inference(respond, command)
    logger.info("実取引推論ハンドラが設定されました (/inference)")
