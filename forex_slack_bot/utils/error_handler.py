"""
エラーハンドラ - エラーハンドリング共通関数
"""

import logging
import traceback
from datetime import datetime
from typing import Optional, Any
import json

from utils.slack_utils import SlackUtils
from config import Config

logger = logging.getLogger(__name__)

class ErrorHandler:
    """エラーハンドリングクラス"""
    
    def __init__(self):
        self.slack_utils = SlackUtils()
        
    async def handle_error(self, respond, error: Exception, context: str = "") -> None:
        """
        エラーを統一的に処理
        
        Args:
            respond: Slack応答関数
            error: 発生したエラー
            context: エラーの文脈情報
        """
        try:
            # エラーの詳細をログに記録
            self._log_error(error, context)
            
            # ユーザーフレンドリーなエラーメッセージを生成
            user_message = self._generate_user_error_message(error, context)
            
            # ユーザーにエラーメッセージを送信
            await respond({
                "text": user_message,
                "response_type": "ephemeral"
            })
            
            # 重要なエラーの場合は管理者に通知
            if self._is_critical_error(error):
                await self._notify_admin(error, context)
                
        except Exception as handler_error:
            # エラーハンドラ自体でエラーが発生した場合
            logger.critical(f"エラーハンドラでエラーが発生: {handler_error}")
            try:
                await respond({
                    "text": "❌ 予期しないエラーが発生しました。管理者に連絡してください。",
                    "response_type": "ephemeral"
                })
            except:
                pass  # 最後の手段として無視
    
    def _log_error(self, error: Exception, context: str) -> None:
        """
        エラーを詳細にログに記録
        """
        try:
            error_info = {
                "timestamp": datetime.now().isoformat(),
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context,
                "traceback": traceback.format_exc()
            }
            
            # JSONフォーマットでログ出力
            logger.error(f"Error occurred: {json.dumps(error_info, indent=2)}")
            
        except Exception as log_error:
            # ログ記録でエラーが発生した場合
            logger.critical(f"ログ記録中にエラー: {log_error}")
            logger.error(f"Original error: {error}")
    
    def _generate_user_error_message(self, error: Exception, context: str) -> str:
        """
        ユーザー向けのエラーメッセージを生成
        """
        error_str = str(error).lower()
        
        # エラーの種類に応じてユーザーフレンドリーなメッセージを生成
        if "timeout" in error_str:
            return "⏱️ 処理がタイムアウトしました。しばらくしてから再度お試しください。"
        
        elif "network" in error_str or "connection" in error_str:
            return "🌐 ネットワークエラーが発生しました。接続を確認してから再度お試しください。"
        
        elif "permission" in error_str or "unauthorized" in error_str:
            return "🔒 権限エラーです。この操作を実行する権限がありません。"
        
        elif "not found" in error_str:
            return "🔍 要求されたリソースが見つかりませんでした。"
        
        elif "invalid" in error_str or "format" in error_str:
            return "❌ 入力形式が正しくありません。コマンドの使用方法を確認してください。"
        
        elif "memory" in error_str or "gpu" in error_str:
            return "💾 メモリ不足またはGPUエラーが発生しました。しばらくしてから再度お試しください。"
        
        elif "rate limit" in error_str:
            return "🚦 APIの利用制限に達しました。しばらくしてから再度お試しください。"
        
        else:
            # 一般的なエラーメッセージ
            base_message = "❌ 予期しないエラーが発生しました。"
            
            if context:
                base_message += f"（{context}）"
            
            base_message += "\n\n管理者に連絡するか、しばらくしてから再度お試しください。"
            
            return base_message
    
    def _is_critical_error(self, error: Exception) -> bool:
        """
        重要なエラーかどうかを判定
        """
        critical_error_types = [
            "DatabaseError",
            "ConnectionError",
            "SecurityError",
            "AuthenticationError",
            "FileNotFoundError"  # 設定ファイルなど重要なファイルの場合
        ]
        
        error_type = type(error).__name__
        error_str = str(error).lower()
        
        # エラータイプによる判定
        if error_type in critical_error_types:
            return True
        
        # エラーメッセージの内容による判定
        critical_keywords = [
            "database",
            "config",
            "authentication",
            "security",
            "permission denied",
            "access denied"
        ]
        
        for keyword in critical_keywords:
            if keyword in error_str:
                return True
        
        return False
    
    async def _notify_admin(self, error: Exception, context: str) -> None:
        """
        管理者にエラー通知を送信
        """
        try:
            if not Config.ADMIN_CHANNEL:
                logger.warning("管理者チャンネルが設定されていません")
                return
            
            error_details = [
                "🚨 **重要なエラーが発生しました**",
                "",
                f"**発生時刻:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"**エラータイプ:** {type(error).__name__}",
                f"**エラーメッセージ:** {str(error)}",
                f"**文脈:** {context}",
                "",
                "**スタックトレース:**",
                f"```{traceback.format_exc()}```",
                "",
                "対応が必要な可能性があります。確認をお願いします。"
            ]
            
            await self.slack_utils.send_message(
                channel_id=Config.ADMIN_CHANNEL,
                text="\n".join(error_details)
            )
            
        except Exception as notification_error:
            logger.error(f"管理者通知送信中にエラー: {notification_error}")
    
    def handle_sync_error(self, error: Exception, context: str = "") -> str:
        """
        同期的なエラーハンドリング（Slack応答なし）
        
        Args:
            error: 発生したエラー
            context: エラーの文脈情報
            
        Returns:
            ユーザー向けエラーメッセージ
        """
        try:
            # エラーをログに記録
            self._log_error(error, context)
            
            # ユーザーメッセージを生成
            return self._generate_user_error_message(error, context)
            
        except Exception as handler_error:
            logger.critical(f"同期エラーハンドラでエラー: {handler_error}")
            return "❌ 予期しないエラーが発生しました。管理者に連絡してください。"
    
    def log_warning(self, message: str, context: str = "") -> None:
        """
        警告をログに記録
        """
        try:
            warning_info = {
                "timestamp": datetime.now().isoformat(),
                "level": "WARNING",
                "message": message,
                "context": context
            }
            
            logger.warning(f"Warning: {json.dumps(warning_info)}")
            
        except Exception as log_error:
            logger.error(f"警告ログ記録中にエラー: {log_error}")
    
    def log_info(self, message: str, context: str = "") -> None:
        """
        情報をログに記録
        """
        try:
            info_data = {
                "timestamp": datetime.now().isoformat(),
                "level": "INFO",
                "message": message,
                "context": context
            }
            
            logger.info(f"Info: {json.dumps(info_data)}")
            
        except Exception as log_error:
            logger.error(f"情報ログ記録中にエラー: {log_error}")
    
    async def handle_api_error(self, respond, api_name: str, error: Exception, retry_count: int = 0) -> None:
        """
        API関連のエラーを処理
        """
        try:
            context = f"{api_name} API呼び出し"
            
            if retry_count > 0:
                context += f" (リトライ {retry_count} 回目)"
            
            error_message = f"🌐 {api_name} APIでエラーが発生しました。"
            
            # APIエラーの種類に応じてメッセージを調整
            if "rate limit" in str(error).lower():
                error_message += "\n利用制限に達しました。しばらくしてから再度お試しください。"
            elif "timeout" in str(error).lower():
                error_message += "\nAPIがタイムアウトしました。"
            elif "unauthorized" in str(error).lower():
                error_message += "\nAPI認証に失敗しました。設定を確認してください。"
            else:
                error_message += f"\nエラー詳細: {str(error)}"
            
            await respond({
                "text": error_message,
                "response_type": "ephemeral"
            })
            
            # ログに記録
            self._log_error(error, context)
            
        except Exception as handler_error:
            logger.error(f"APIエラーハンドラでエラー: {handler_error}")
    
    def create_error_report(self, error: Exception, context: str = "") -> dict:
        """
        エラーレポートを作成
        """
        try:
            return {
                "timestamp": datetime.now().isoformat(),
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context,
                "traceback": traceback.format_exc(),
                "severity": "critical" if self._is_critical_error(error) else "normal"
            }
            
        except Exception as report_error:
            logger.error(f"エラーレポート作成中にエラー: {report_error}")
            return {
                "timestamp": datetime.now().isoformat(),
                "error": "Failed to create error report",
                "original_error": str(error)
            }