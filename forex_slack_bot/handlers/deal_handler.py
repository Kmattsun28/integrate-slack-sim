"""
取引ハンドラ - !deal, !deal-log, !deal-undo, !deal-redo コマンド処理
"""

import logging
import re
from typing import List, Optional

from services.trading_service import TradingService
from utils.slack_utils import SlackUtils

logger = logging.getLogger(__name__)

class DealHandler:
    """取引コマンドのハンドラクラス"""
    
    def __init__(self):
        self.trading_service = TradingService()
        self.slack_utils = SlackUtils()
    
    async def handle_deal(self, respond, command):
        """
        !deal {通貨ペア} {±金額} {スプレッド含んだレート} コマンドの処理
        例: !deal USDJPY +300 172.4
        """
        try:
            text = command.get("text", "").strip()
            
            # コマンドをパース
            parsed_params = self._parse_deal_command(text)
            if not parsed_params:
                respond({
                    "text": "❌ コマンド形式が正しくありません。\n使用方法: `/deal {通貨ペア} {±金額} {レート}`\n例: `/deal USDJPY +300 172.4`",
                    "response_type": "ephemeral"
                })
                return
            
            currency_pair, amount, rate = parsed_params
            user_id = command.get("user_id")
            
            # 取引を実行
            result = await self.trading_service.execute_trade(
                currency_pair=currency_pair,
                amount=amount,
                rate=rate,
                user_id=user_id
            )
            
            if result["success"]:
                # 成功時のレスポンス
                balance_text = self._format_balance_summary(result["new_balance"])
                respond({
                    "text": f"✅ 取引が完了しました！\n\n📈 取引詳細:\n{currency_pair}: {'+' if amount > 0 else ''}{amount} @ {rate}\n\n💰 更新後の残高:\n{balance_text}",
                    "response_type": "in_channel"
                })
            else:
                # 失敗時のレスポンス
                respond({
                    "text": f"❌ 取引に失敗しました: {result['error']}",
                    "response_type": "ephemeral"
                })
                
        except Exception as e:
            logger.error(f"取引コマンド処理中にエラーが発生: {e}")
            respond({
                "text": f"❌ 取引処理中にエラーが発生しました: {str(e)}",
                "response_type": "ephemeral"
            })
    
    def handle_deal_log(self, respond, command):
        """
        !deal-log コマンドの処理（DMのみに応答）
        """
        try:
            # DMかどうかをチェック
            if not self._is_direct_message(command):
                respond({
                    "text": "🔒 取引ログはDM（ダイレクトメッセージ）でのみ確認できます。",
                    "response_type": "ephemeral"
                })
                return
            
            # 取引ログを取得
            transaction_logs = self.trading_service.get_transaction_logs()
            
            if not transaction_logs:
                respond({
                    "text": "📝 取引ログはまだありません。",
                    "response_type": "ephemeral"
                })
                return
            
            # ログをフォーマット
            log_text = self._format_transaction_logs(transaction_logs)
            
            respond({
                "text": f"📊 取引ログ:\n```\n{log_text}\n```",
                "response_type": "ephemeral"
            })
            
        except Exception as e:
            logger.error(f"取引ログ取得中にエラーが発生: {e}")
            respond({
                "text": f"❌ 取引ログ取得中にエラーが発生しました: {str(e)}",
                "response_type": "ephemeral"
            })
    
    def handle_deal_undo(self, respond, command):
        """
        !deal-undo コマンドの処理
        最新の取引を無かったことにする
        """
        try:
            user_id = command.get("user_id")
            # 取引履歴のundo時に残高・ログを復元
            self.trading_service.balance_manager._restore_from_backup()
            self.trading_service.transaction_log._restore_from_backup()
            
            # 取引を取り消し
            result = self.trading_service.undo_last_transaction(user_id)
            
            if result["success"]:
                balance_text = self._format_balance_summary(result["new_balance"])
                respond({
                    "text": f"↩️ 最新の取引を取り消しました。\n\n📊 取り消された取引:\n{result['undone_transaction']}\n\n💰 更新後の残高:\n{balance_text}",
                    "response_type": "in_channel"
                })
            else:
                respond({
                    "text": f"❌ 取引の取り消しに失敗しました: {result['error']}",
                    "response_type": "ephemeral"
                })
                
        except Exception as e:
            logger.error(f"取引取り消し中にエラーが発生: {e}")
            respond({
                "text": f"❌ 取引取り消し中にエラーが発生しました: {str(e)}",
                "response_type": "ephemeral"
            })
    
    def handle_deal_redo(self, respond, command):
        """
        !deal-redo コマンドの処理
        undoした内容をもう一度実行する
        """
        try:
            user_id = command.get("user_id")
            # redo時も同様に残高・ログを復元
            self.trading_service.balance_manager._restore_from_backup()
            self.trading_service.transaction_log._restore_from_backup()
            
            # 取引をやり直し
            result = self.trading_service.redo_last_transaction(user_id)
            
            if result["success"]:
                balance_text = self._format_balance_summary(result["new_balance"])
                respond({
                    "text": f"↪️ 取引をやり直しました。\n\n📊 やり直した取引:\n{result['redone_transaction']}\n\n💰 更新後の残高:\n{balance_text}",
                    "response_type": "in_channel"
                })
            else:
                respond({
                    "text": f"❌ 取引のやり直しに失敗しました: {result['error']}",
                    "response_type": "ephemeral"
                })
                
        except Exception as e:
            logger.error(f"取引やり直し中にエラーが発生: {e}")
            respond({
                "text": f"❌ 取引やり直し中にエラーが発生しました: {str(e)}",
                "response_type": "ephemeral"
            })
    
    def _parse_deal_command(self, text: str) -> Optional[tuple]:
        """
        !deal コマンドのパラメータをパース
        戻り値: (currency_pair, amount, rate) または None
        """
        # 正規表現でパラメータを抽出
        pattern = r'^(\w+)\s+([\+\-]?\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)$'
        match = re.match(pattern, text)
        
        if not match:
            return None
        
        currency_pair = match.group(1).upper()
        amount = float(match.group(2))
        rate = float(match.group(3))
        
        return currency_pair, amount, rate
    
    def _is_direct_message(self, command) -> bool:
        """
        DMかどうかを判定
        """
        channel_name = command.get("channel_name", "")
        return channel_name.startswith("D") or channel_name == "directmessage"
    
    def _format_balance_summary(self, balance: dict) -> str:
        """
        残高を見やすくフォーマット
        """
        lines = []
        for currency, amount in balance.items():
            lines.append(f"{currency}: {amount:,.2f}")
        return "\n".join(lines)
    
    def _format_transaction_logs(self, logs: List[dict]) -> str:
        """
        取引ログを見やすくフォーマット
        """
        lines = []
        lines.append("日時                 | 通貨ペア | 金額      | レート   | 種別")
        lines.append("-" * 60)
        
        for log in logs[-20:]:  # 最新20件のみ表示
            timestamp = log.get("timestamp", "")
            pair = log.get("currency_pair", "")
            amount = log.get("amount", 0)
            rate = log.get("rate", 0)
            transaction_type = log.get("type", "取引")
            
            amount_str = f"{'+' if amount > 0 else ''}{amount:,.0f}"
            lines.append(f"{timestamp} | {pair:8} | {amount_str:9} | {rate:8.2f} | {transaction_type}")
        
        return "\n".join(lines)


def setup_deal_handlers(app, deal_handler, error_handler):
    """
    取引関連のハンドラーを設定
    """
    @app.command("/deal")
    def handle_deal_command(ack, respond, command):
        ack()
        try:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            loop.run_until_complete(deal_handler.handle_deal(respond, command))
        except Exception as e:
            error_handler.handle_error(respond, e, "取引コマンドの実行中")

    @app.command("/deal-log")
    def handle_deal_log_command(ack, respond, command):
        ack()
        try:
            deal_handler.handle_deal_log(respond, command)
        except Exception as e:
            error_handler.handle_error(respond, e, "取引ログコマンドの実行中")

    @app.command("/deal-undo")
    def handle_deal_undo_command(ack, respond, command):
        ack()
        try:
            deal_handler.handle_deal_undo(respond, command)
        except Exception as e:
            error_handler.handle_error(respond, e, "取引取り消しコマンドの実行中")

    @app.command("/deal-redo")
    def handle_deal_redo_command(ack, respond, command):
        ack()
        try:
            deal_handler.handle_deal_redo(respond, command)
        except Exception as e:
            error_handler.handle_error(respond, e, "取引やり直しコマンドの実行中")