"""
共通ハンドラ - ヘルプなどの共通機能
"""

import logging
from config import Config

logger = logging.getLogger(__name__)

class CommonHandlers:
    """共通機能のハンドラクラス"""
    
    def handle_help(self, respond, command):
        """
        !help コマンドの処理
        利用可能なコマンドの一覧を表示
        """
        try:
            help_text = self._generate_help_text()
            
            respond({
                "text": help_text,
                "response_type": "ephemeral"
            })
            
        except Exception as e:
            logger.error(f"ヘルプ表示中にエラーが発生: {e}")
            respond({
                "text": f"❌ ヘルプ表示中にエラーが発生しました: {str(e)}",
                "response_type": "ephemeral"
            })
    
    def _generate_help_text(self) -> str:
        """
        ヘルプテキストを生成
        """
        help_lines = [
            "🤖 **為替取引Bot ヘルプ**",
            "",
            "**📊 推論・分析系コマンド**",
            "`/inference` - AI推論を実行（非同期処理、結果はファイル添付）",
            "`/run_inference` - シミュレータ連携AI推論を実行",
            "`/run_analysis` - 取引データの分析実行",
            "`/simulator_status` - シミュレータの状態確認",
            "",
            "**💰 取引系コマンド**",
            "`/deal {通貨ペア} {±金額} {レート}` - 取引実行",
            "  例: `/deal USDJPY +300 172.4`",
            "`/deal-undo` - 最新の取引を取り消し",
            "`/deal-redo` - 取り消した取引をやり直し",
            "`/deal-log` - 取引ログ表示（DMのみ）",
            "",
            "**💳 残高系コマンド**",
            "`/balance` - 現在の残高表示（DMのみ）",
            "`/balance-override {通貨} {金額}` - 残高上書き（管理者のみ）",
            "",
            "**🛠️ その他**",
            "`/help` - このヘルプを表示",
            "",
            "**📝 利用上の注意**",
            "• 残高確認と取引ログはDM（ダイレクトメッセージ）でのみ確認可能",
            "• 推論は非同期で実行され、完了次第結果が通知されます",
            "• 一度に実行できる推論は1つまで",
            "",
            f"**💱 サポート対象通貨**",
            f"{', '.join(Config.SUPPORTED_CURRENCIES)}",
            "",
            "**🔧 設定**",
        ]
        
        # 定期推論設定の表示
        if Config.PERIODIC_INFERENCE_ENABLED:
            help_lines.append(f"• 定期推論: {Config.PERIODIC_INFERENCE_INTERVAL_HOURS}時間間隔で自動実行")
        else:
            help_lines.append("• 定期推論: 無効")
        
        help_lines.extend([
            "",
            "**❓ 問題が発生した場合**",
            "管理者までお問い合わせください。",
            "",
            "---",
            "*Forex Trading Bot v1.0*"
        ])
        
        return "\n".join(help_lines)


def setup_common_handlers(app, common_handlers, error_handler):
    """
    共通ハンドラーを設定
    """
    @app.command("/help")
    def handle_help_command(ack, respond, command):
        ack()
        try:
            common_handlers.handle_help(respond, command)
        except Exception as e:
            error_handler.handle_error(respond, e, "ヘルプコマンドの実行中")