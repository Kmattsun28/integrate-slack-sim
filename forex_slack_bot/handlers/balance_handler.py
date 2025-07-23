"""
残高ハンドラ - !balance, !balance-override コマンド処理
"""

import logging
import re
from typing import Optional

from services.trading_service import TradingService
from services.rate_service import RateService
from utils.slack_utils import SlackUtils
from config import Config

logger = logging.getLogger(__name__)

class BalanceHandler:
    """残高コマンドのハンドラクラス"""
    
    def __init__(self):
        self.trading_service = TradingService()
        self.rate_service = RateService()
        self.slack_utils = SlackUtils()
    
    async def handle_balance(self, respond, command):
        """
        !balance コマンドの処理（DMのみに応答）
        現在の総資産を表示し、可能であれば日本円換算も表示
        """
        try:
            # DMかどうかをチェック
            if not self._is_direct_message(command):
                respond({
                    "text": "🔒 残高確認はDM（ダイレクトメッセージ）でのみ可能です。",
                    "response_type": "ephemeral"
                })
                return

            # 現在の残高を取得
            current_balance = self.trading_service.get_current_balance()

            # 日本円換算を計算（awaitで非同期対応）
            jpy_total = await self._calculate_jpy_total(current_balance)

            # 計算時刻を取得
            from datetime import datetime
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
            # 残高情報をフォーマット（時刻付き）
            balance_text = self._format_detailed_balance(current_balance, jpy_total, now_str)

            respond({
                "text": f"💰 現在の資産状況\n```\n{balance_text}\n```",
                "response_type": "ephemeral"
            })

        except Exception as e:
            logger.error(f"残高確認中にエラーが発生: {e}")
            respond({
                "text": f"❌ 残高確認中にエラーが発生しました: {str(e)}",
                "response_type": "ephemeral"
            })

    async def _calculate_jpy_total(self, balance: dict):
        """
        総資産を日本円で計算（非同期版）
        """
        try:
            total_jpy = 0.0
            for currency, amount in balance.items():
                if currency == "JPY":
                    total_jpy += amount
                else:
                    pair = f"{currency}JPY"
                    rate = await self.rate_service.get_current_rate(pair)
                    if rate:
                        total_jpy += amount * rate
                    else:
                        logger.warning(f"{pair}のレート取得に失敗しました")
                        return None
            return total_jpy
        except Exception as e:
            logger.error(f"JPY換算計算中にエラー: {e}")
            return None
    
    def handle_balance_override(self, respond, command):
        """
        !balance-override {通貨} {金額} コマンドの処理
        特定通貨の残高を上書き更新（確認付きの破壊的操作）
        """
        try:
            text = command.get("text", "").strip()
            
            # コマンドをパース
            parsed_params = self._parse_balance_override_command(text)
            if not parsed_params:
                respond({
                    "text": "❌ コマンド形式が正しくありません。\n使用方法: `/balance-override {通貨} {金額}`\n例: `/balance-override JPY 1000000`",
                    "response_type": "ephemeral"
                })
                return
            
            currency, amount = parsed_params
            user_id = command.get("user_id")
            
            # 管理者権限チェック
            if not self._is_admin_user(user_id):
                respond({
                    "text": "❌ この操作には管理者権限が必要です。",
                    "response_type": "ephemeral"
                })
                return
            
            # 現在の残高を取得
            current_balance = self.trading_service.get_current_balance()
            current_amount = current_balance.get(currency, 0)
            
            # 確認メッセージ
            confirmation_text = f"⚠️ **残高上書き確認**\n\n"
            confirmation_text += f"通貨: {currency}\n"
            confirmation_text += f"現在の残高: {current_amount:,.2f}\n"
            confirmation_text += f"新しい残高: {amount:,.2f}\n\n"
            confirmation_text += f"この操作は元に戻せません。本当に実行しますか？\n"
            confirmation_text += f"実行する場合は `/balance-override-confirm {currency} {amount}` と入力してください。"
            
            respond({
                "text": confirmation_text,
                "response_type": "ephemeral"
            })
            
        except Exception as e:
            logger.error(f"残高上書き処理中にエラーが発生: {e}")
            respond({
                "text": f"❌ 残高上書き処理中にエラーが発生しました: {str(e)}",
                "response_type": "ephemeral"
            })

    def handle_balance_override_confirm(self, respond, command):
        """
        残高上書きの確認コマンド処理
        """
        try:
            text = command.get("text", "").strip()
            
            # コマンドをパース
            parsed_params = self._parse_balance_override_command(text)
            if not parsed_params:
                respond({
                    "text": "❌ 確認コマンド形式が正しくありません。",
                    "response_type": "ephemeral"
                })
                return
            
            currency, amount = parsed_params
            user_id = command.get("user_id")
            
            # 管理者権限チェック
            if not self._is_admin_user(user_id):
                respond({
                    "text": "❌ この操作には管理者権限が必要です。",
                    "response_type": "ephemeral"
                })
                return
            
            # 残高を上書き
            result = self.trading_service.override_balance(
                currency=currency,
                new_amount=amount,
                user_id=user_id
            )
            
            if result["success"]:
                balance_text = self._format_balance_summary(result["new_balance"])
                respond({
                    "text": f"✅ {currency}の残高を{amount:,.2f}に上書きしました。\n\n💰 更新後の残高:\n{balance_text}",
                    "response_type": "in_channel"
                })
            else:
                respond({
                    "text": f"❌ 残高上書きに失敗しました: {result['error']}",
                    "response_type": "ephemeral"
                })
                
        except Exception as e:
            logger.error(f"残高上書き確認処理中にエラーが発生: {e}")
            respond({
                "text": f"❌ 残高上書き確認処理中にエラーが発生しました: {str(e)}",
                "response_type": "ephemeral"
            })
    
    def _parse_balance_override_command(self, text: str) -> Optional[tuple]:
        """
        balance-override コマンドのパラメータをパース
        戻り値: (currency, amount) または None
        """
        pattern = r'^(\w+)\s+(\d+(?:\.\d+)?)$'
        match = re.match(pattern, text)
        
        if not match:
            return None
        
        currency = match.group(1).upper()
        amount = float(match.group(2))
        
        # サポート対象通貨かチェック
        if currency not in Config.SUPPORTED_CURRENCIES:
            return None
        
        return currency, amount
    
    def _is_direct_message(self, command) -> bool:
        """
        DMかどうかを判定
        """
        channel_name = command.get("channel_name", "")
        return channel_name.startswith("D") or channel_name == "directmessage"
    
    def _is_admin_user(self, user_id: str) -> bool:
        """
        管理者ユーザーかどうかを判定
        """
        return user_id in Config.ADMIN_USER_IDS
    
    def _format_detailed_balance(self, balance: dict, jpy_total: Optional[float], calc_time: str = None) -> str:
        """
        詳細な残高情報をフォーマット
        """
        lines = []
        lines.append("通貨    | 残高")
        lines.append("-" * 20)
        
        for currency in Config.SUPPORTED_CURRENCIES:
            amount = balance.get(currency, 0)
            if amount != 0 or currency == "JPY":  # JPYは常に表示
                lines.append(f"{currency:7} | {amount:>12,.2f}")
        
        lines.append("-" * 20)
        
        if jpy_total is not None:
            lines.append(f"日本円換算総額: ¥{jpy_total:,.0f}")
            if calc_time:
                lines.append(f"（{calc_time} 時点の総額）")
        else:
            lines.append("日本円換算総額: 計算不可")
        
        return "\n".join(lines)
    
    def _format_balance_summary(self, balance: dict) -> str:
        """
        残高を見やすくフォーマット（簡易版）
        """
        lines = []
        for currency, amount in balance.items():
            if amount != 0 or currency == "JPY":
                lines.append(f"{currency}: {amount:,.2f}")
        return "\n".join(lines)


def setup_balance_handlers(app, balance_handler, error_handler):
    """
    残高関連のハンドラーを設定
    """
    @app.command("/balance")
    def handle_balance_command(ack, respond, command):
        ack()
        try:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            loop.run_until_complete(balance_handler.handle_balance(respond, command))
        except Exception as e:
            error_handler.handle_error(respond, e, "残高コマンドの実行中")

    @app.command("/balance-override")
    def handle_balance_override_command(ack, respond, command):
        ack()
        try:
            balance_handler.handle_balance_override(respond, command)
        except Exception as e:
            error_handler.handle_error(respond, e, "残高上書きコマンドの実行中")