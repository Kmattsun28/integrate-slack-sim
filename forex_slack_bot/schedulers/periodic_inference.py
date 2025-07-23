"""
定期推論スケジューラ - 実取引データ専用定期推論（シミュレーション機能削除版）
"""

import asyncio
import logging
import tempfile
from datetime import datetime
from typing import Optional

from services.inference_service import InferenceService
from services.trading_service import TradingService
from services.rate_service import RateService
from utils.slack_utils import SlackUtils
from config import Config

logger = logging.getLogger(__name__)

class PeriodicInference:
    """実取引データ専用定期推論実行クラス"""
    
    def __init__(self):
        self.inference_service = InferenceService()
        self.trading_service = TradingService()
        self.rate_service = RateService()
        self.slack_utils = SlackUtils()
        
    def run_periodic_inference(self):
        """
        定期推論を実行（実取引データのみ使用）
        手動推論とバッティングしないようにロック機構を使用
        """
        try:
            logger.info("定期推論を開始します（実取引データ使用）")
            
            # 推論が既に実行中かチェック
            if self.inference_service.is_inference_running():
                logger.info("推論が既に実行中のため、定期推論をスキップします")
                return
            
            # 非同期で推論を実行
            asyncio.run(self._run_periodic_inference_async())
            
        except Exception as e:
            logger.error(f"定期推論実行中にエラー: {e}")
            # エラーが発生した場合、管理チャンネルに通知
            asyncio.run(self._send_error_notification(e))
    
    async def _run_periodic_inference_async(self):
        """
        非同期での定期推論実行（実取引データ専用）
        """
        try:
            # 現在の残高を取得
            current_balance = self.trading_service.get_current_balance()
            
            # レート取得時刻を記録
            rate_fetch_time = datetime.now()
            
            # 実取引データ推論を実行
            inference_result = await self.inference_service.run_inference(current_balance)
            
            # 結果をフォーマット
            result_text = self._format_periodic_inference_result(
                inference_result, 
                rate_fetch_time
            )
            
            # 結果をテキストファイルとして保存
            temp_file_path = await self._save_result_to_temp_file(result_text)
            
            filename = f"periodic_inference_real_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            # デフォルトチャンネルに結果を送信
            await self.slack_utils.send_message_with_file(
                channel_id=Config.DEFAULT_CHANNEL,
                text="🤖 **定期推論結果**（実取引データ使用）\n\n自動推論が完了しました。結果をご確認ください。",
                file_path=temp_file_path,
                filename=filename
            )
            
            # 推奨取引がある場合は別途通知
            if inference_result.get("recommended_trades"):
                await self._send_trade_recommendations(inference_result["recommended_trades"])
            
            logger.info("実取引データ定期推論が正常に完了しました")
            
        except Exception as e:
            logger.error(f"定期推論実行中にエラー: {e}")
            await self._send_error_notification(e)
        finally:
            # 推論状態をリセット
            self.inference_service.reset_inference_state()
    
    def _format_periodic_inference_result(self, result: dict, rate_fetch_time: datetime) -> str:
        """
        定期推論結果をフォーマット（実取引データ専用）
        """
        formatted_text = []
        
        data_source = result.get("data_source", "real_trading_data")
        
        formatted_text.append("=" * 60)
        formatted_text.append("🤖 実取引データ定期推論レポート")
        formatted_text.append("=" * 60)
        formatted_text.append(f"推論実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        formatted_text.append(f"レート取得日時: {rate_fetch_time.strftime('%Y-%m-%d %H:%M:%S')}")
        formatted_text.append(f"データソース: {data_source}")
        formatted_text.append("")
        
        # 市場データの表示
        if result.get("market_data"):
            formatted_text.append("📊 現在の市場状況:")
            market_data = result["market_data"]
            
            if market_data.get("rates"):
                for pair, rate in market_data["rates"].items():
                    trend = market_data.get("trends", {}).get(pair, "不明")
                    formatted_text.append(f"  {pair}: {rate:.2f} (トレンド: {trend})")
            formatted_text.append("")
        
        # 推奨取引がある場合
        if result.get("recommended_trades"):
            formatted_text.append("💡 AI推奨取引（実取引データ分析）:")
            for i, trade in enumerate(result["recommended_trades"], 1):
                action = "🟢 買い推奨" if trade.get("action") == "buy" else "🔴 売り推奨"
                confidence = trade.get("confidence", 0) * 100
                formatted_text.append(f"{i}. {trade.get('pair')}: {action}")
                formatted_text.append(f"   推奨金額: {trade.get('amount', 0):.2f}")
                formatted_text.append(f"   目標レート: {trade.get('rate', 0):.2f}")
                formatted_text.append(f"   信頼度: {confidence:.0f}%")
                if trade.get("reasoning"):
                    formatted_text.append(f"   理由: {trade.get('reasoning')}")
                formatted_text.append("")
        else:
            formatted_text.append("💡 推奨取引: 現時点では新しい取引を推奨しません")
            formatted_text.append("")
        
        # 現在の残高情報
        if result.get("current_balance"):
            formatted_text.append("💰 現在のポートフォリオ:")
            total_jpy = 0
            for currency, amount in result["current_balance"].items():
                formatted_text.append(f"  {currency}: {amount:,.2f}")
                # JPY換算（概算）
                if currency == "JPY":
                    total_jpy += amount
                elif currency == "USD":
                    total_jpy += amount * result.get("market_data", {}).get("rates", {}).get("USDJPY", 150)
                elif currency == "EUR":
                    total_jpy += amount * result.get("market_data", {}).get("rates", {}).get("EURJPY", 160)
            
            formatted_text.append(f"  総価値（概算）: ¥{total_jpy:,.2f}")
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
            formatted_text.append("🔍 実取引データ分析サマリー:")
            formatted_text.append(result["real_data_summary"])
            formatted_text.append("")
        
        # 免責事項
        formatted_text.append("=" * 60)
        formatted_text.append("⚠️  重要な注意事項")
        formatted_text.append("=" * 60)
        formatted_text.append("• この推論結果は実際の取引データに基づく自動分析です")
        formatted_text.append("• 投資助言ではありません")
        formatted_text.append("• 為替取引にはリスクが伴います")
        formatted_text.append("• 取引の判断は自己責任で行ってください")
        
        return "\\n".join(formatted_text)
    
    async def _save_result_to_temp_file(self, text: str) -> str:
        """
        結果を一時ファイルに保存
        """
        loop = asyncio.get_event_loop()
        
        def write_file():
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                f.write(text)
                return f.name
        
        return await loop.run_in_executor(None, write_file)
    
    async def _send_trade_recommendations(self, recommendations: list):
        """
        推奨取引の個別通知
        """
        if not recommendations:
            return
        
        message_lines = ["🚨 **取引推奨アラート**（実取引データ分析）", ""]
        
        for i, trade in enumerate(recommendations, 1):
            action_emoji = "🟢" if trade.get("action") == "buy" else "🔴"
            action_text = "買い" if trade.get("action") == "buy" else "売り"
            confidence = trade.get("confidence", 0) * 100
            
            message_lines.append(f"{action_emoji} **{trade.get('pair')}**: {action_text}推奨")
            message_lines.append(f"   金額: {trade.get('amount', 0):.2f}")
            message_lines.append(f"   レート: {trade.get('rate', 0):.2f}")
            message_lines.append(f"   信頼度: {confidence:.0f}%")
            if trade.get("reasoning"):
                message_lines.append(f"   理由: {trade.get('reasoning')}")
            message_lines.append("")
        
        message_lines.append("⚠️ 投資判断は慎重に行ってください")
        
        await self.slack_utils.send_message(
            channel_id=Config.DEFAULT_CHANNEL,
            text="\\n".join(message_lines)
        )
    
    async def _send_error_notification(self, error: Exception):
        """
        エラー通知を送信
        """
        try:
            error_message = f"❌ **定期推論エラー**\n\n" \
                           f"時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" \
                           f"エラー: {str(error)[:200]}\n\n" \
                           f"システム管理者に確認を依頼してください。"
            
            # 管理チャンネルまたはデフォルトチャンネルに送信
            notification_channel = getattr(Config, 'ADMIN_CHANNEL', Config.DEFAULT_CHANNEL)
            
            await self.slack_utils.send_message(
                channel_id=notification_channel,
                text=error_message
            )
        except Exception as notification_error:
            logger.error(f"エラー通知送信に失敗: {notification_error}")
    
    async def send_manual_status_update(self):
        """
        手動での推論ステータス更新（管理用）
        """
        try:
            status = "🔄 実行中" if self.inference_service.is_inference_running() else "⏹️ 停止中"
            
            message = f"🤖 **定期推論ステータス**\n\n" \
                     f"現在の状態: {status}\n" \
                     f"確認日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" \
                     f"データソース: 実取引データ専用"
            
            await self.slack_utils.send_message(
                channel_id=Config.DEFAULT_CHANNEL,
                text=message
            )
            
        except Exception as e:
            logger.error(f"ステータス更新送信に失敗: {e}")
