"""
Slackユーティリティ - Slack APIとの連携ヘルパー
"""

import logging
import os
from typing import Optional, Dict, Any
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from config import Config

logger = logging.getLogger(__name__)

class SlackUtils:
    """Slack API連携ユーティリティクラス"""
    
    def __init__(self):
        self.client = WebClient(token=Config.SLACK_BOT_TOKEN)
        
    async def send_message(self, channel_id: str, text: str, **kwargs) -> bool:
        """
        メッセージを送信
        
        Args:
            channel_id: 送信先チャンネルID
            text: メッセージテキスト
            **kwargs: その他のSlack API パラメータ
            
        Returns:
            送信成功の場合True
        """
        try:
            response = self.client.chat_postMessage(
                channel=channel_id,
                text=text,
                **kwargs
            )
            
            if response["ok"]:
                logger.debug(f"メッセージを送信しました: {channel_id}")
                return True
            else:
                logger.error(f"メッセージ送信に失敗: {response.get('error', 'Unknown error')}")
                return False
                
        except SlackApiError as e:
            logger.error(f"Slack API エラー: {e.response['error']}")
            return False
        except Exception as e:
            logger.error(f"メッセージ送信中にエラー: {e}")
            return False
    
    async def send_message_with_file(self, channel_id: str, text: str, file_path: str, 
                                   filename: Optional[str] = None, **kwargs) -> bool:
        """
        ファイル添付付きメッセージを送信
        
        Args:
            channel_id: 送信先チャンネルID
            text: メッセージテキスト
            file_path: 添付ファイルのパス
            filename: 表示用ファイル名
            **kwargs: その他のパラメータ
            
        Returns:
            送信成功の場合True
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"添付ファイルが見つかりません: {file_path}")
                return False
            
            # ファイル名を設定
            if filename is None:
                filename = os.path.basename(file_path)
            
            # ファイルをアップロード
            response = self.client.files_upload_v2(
                channel=channel_id,
                file=file_path,
                filename=filename,
                initial_comment=text,
                **kwargs
            )
            
            if response["ok"]:
                logger.debug(f"ファイル付きメッセージを送信しました: {channel_id}, {filename}")
                
                # 一時ファイルの場合は削除
                if "/tmp/" in file_path or "temp" in file_path.lower():
                    try:
                        os.remove(file_path)
                        logger.debug(f"一時ファイルを削除しました: {file_path}")
                    except Exception as cleanup_error:
                        logger.warning(f"一時ファイル削除に失敗: {cleanup_error}")
                
                return True
            else:
                logger.error(f"ファイルアップロードに失敗: {response.get('error', 'Unknown error')}")
                return False
                
        except SlackApiError as e:
            logger.error(f"Slack API エラー (ファイルアップロード): {e.response['error']}")
            return False
        except Exception as e:
            logger.error(f"ファイル送信中にエラー: {e}")
            return False
    
    async def send_dm(self, user_id: str, text: str, **kwargs) -> bool:
        """
        ダイレクトメッセージを送信
        
        Args:
            user_id: 送信先ユーザーID
            text: メッセージテキスト
            **kwargs: その他のパラメータ
            
        Returns:
            送信成功の場合True
        """
        try:
            # DMチャンネルを開く
            dm_response = self.client.conversations_open(users=[user_id])
            
            if not dm_response["ok"]:
                logger.error(f"DMチャンネルオープンに失敗: {dm_response.get('error', 'Unknown error')}")
                return False
            
            channel_id = dm_response["channel"]["id"]
            
            # メッセージを送信
            return await self.send_message(channel_id, text, **kwargs)
            
        except SlackApiError as e:
            logger.error(f"Slack API エラー (DM): {e.response['error']}")
            return False
        except Exception as e:
            logger.error(f"DM送信中にエラー: {e}")
            return False
    
    async def send_threaded_message(self, channel_id: str, thread_ts: str, text: str, **kwargs) -> bool:
        """
        スレッド内にメッセージを送信
        
        Args:
            channel_id: 送信先チャンネルID
            thread_ts: スレッドのタイムスタンプ
            text: メッセージテキスト
            **kwargs: その他のパラメータ
            
        Returns:
            送信成功の場合True
        """
        try:
            kwargs["thread_ts"] = thread_ts
            return await self.send_message(channel_id, text, **kwargs)
            
        except Exception as e:
            logger.error(f"スレッドメッセージ送信中にエラー: {e}")
            return False
    
    def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        ユーザー情報を取得
        
        Args:
            user_id: ユーザーID
            
        Returns:
            ユーザー情報辞書、取得失敗時はNone
        """
        try:
            response = self.client.users_info(user=user_id)
            
            if response["ok"]:
                return response["user"]
            else:
                logger.error(f"ユーザー情報取得に失敗: {response.get('error', 'Unknown error')}")
                return None
                
        except SlackApiError as e:
            logger.error(f"Slack API エラー (ユーザー情報): {e.response['error']}")
            return None
        except Exception as e:
            logger.error(f"ユーザー情報取得中にエラー: {e}")
            return None
    
    def get_channel_info(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """
        チャンネル情報を取得
        
        Args:
            channel_id: チャンネルID
            
        Returns:
            チャンネル情報辞書、取得失敗時はNone
        """
        try:
            response = self.client.conversations_info(channel=channel_id)
            
            if response["ok"]:
                return response["channel"]
            else:
                logger.error(f"チャンネル情報取得に失敗: {response.get('error', 'Unknown error')}")
                return None
                
        except SlackApiError as e:
            logger.error(f"Slack API エラー (チャンネル情報): {e.response['error']}")
            return None
        except Exception as e:
            logger.error(f"チャンネル情報取得中にエラー: {e}")
            return None
    
    async def add_reaction(self, channel_id: str, timestamp: str, name: str) -> bool:
        """
        メッセージにリアクションを追加
        
        Args:
            channel_id: チャンネルID
            timestamp: メッセージのタイムスタンプ
            name: リアクション名（例: "thumbsup"）
            
        Returns:
            追加成功の場合True
        """
        try:
            response = self.client.reactions_add(
                channel=channel_id,
                timestamp=timestamp,
                name=name
            )
            
            if response["ok"]:
                logger.debug(f"リアクションを追加しました: {name}")
                return True
            else:
                logger.error(f"リアクション追加に失敗: {response.get('error', 'Unknown error')}")
                return False
                
        except SlackApiError as e:
            logger.error(f"Slack API エラー (リアクション): {e.response['error']}")
            return False
        except Exception as e:
            logger.error(f"リアクション追加中にエラー: {e}")
            return False
    
    def is_direct_message(self, channel_id: str) -> bool:
        """
        チャンネルがダイレクトメッセージかどうかを判定
        
        Args:
            channel_id: チャンネルID
            
        Returns:
            DMの場合True
        """
        try:
            # DMのチャンネルIDは"D"で始まる
            if channel_id.startswith("D"):
                return True
            
            # より確実にチェックするため、チャンネル情報を取得
            channel_info = self.get_channel_info(channel_id)
            if channel_info:
                return channel_info.get("is_im", False)
            
            return False
            
        except Exception as e:
            logger.error(f"DM判定中にエラー: {e}")
            return False
    
    def format_user_mention(self, user_id: str) -> str:
        """
        ユーザーメンション形式の文字列を生成
        
        Args:
            user_id: ユーザーID
            
        Returns:
            メンション文字列
        """
        return f"<@{user_id}>"
    
    def format_channel_mention(self, channel_id: str) -> str:
        """
        チャンネルメンション形式の文字列を生成
        
        Args:
            channel_id: チャンネルID
            
        Returns:
            メンション文字列
        """
        return f"<#{channel_id}>"
    
    async def send_error_message(self, channel_id: str, error: Exception, context: str = "") -> bool:
        """
        エラーメッセージを整形して送信
        
        Args:
            channel_id: 送信先チャンネルID
            error: エラー情報
            context: エラーの文脈情報
            
        Returns:
            送信成功の場合True
        """
        try:
            error_text = f"❌ エラーが発生しました"
            
            if context:
                error_text += f" ({context})"
            
            error_text += f"\n\n詳細: {str(error)}"
            
            return await self.send_message(channel_id, error_text)
            
        except Exception as e:
            logger.error(f"エラーメッセージ送信中にエラー: {e}")
            return False
    
    def validate_channel_access(self, channel_id: str) -> bool:
        """
        チャンネルへのアクセス権限を確認
        
        Args:
            channel_id: チャンネルID
            
        Returns:
            アクセス可能な場合True
        """
        try:
            response = self.client.conversations_info(channel=channel_id)
            return response["ok"]
            
        except SlackApiError as e:
            logger.warning(f"チャンネルアクセス確認失敗: {e.response['error']}")
            return False
        except Exception as e:
            logger.error(f"チャンネルアクセス確認中にエラー: {e}")
            return False
    
    def get_bot_info(self) -> Optional[Dict[str, Any]]:
        """
        Bot自身の情報を取得
        
        Returns:
            Bot情報辞書、取得失敗時はNone
        """
        try:
            response = self.client.auth_test()
            
            if response["ok"]:
                return response
            else:
                logger.error(f"Bot情報取得に失敗: {response.get('error', 'Unknown error')}")
                return None
                
        except SlackApiError as e:
            logger.error(f"Slack API エラー (Bot情報): {e.response['error']}")
            return None
        except Exception as e:
            logger.error(f"Bot情報取得中にエラー: {e}")
            return None