"""
推論サービス - 実取引データ専用推論システム（シミュレーション機能削除版）
"""

import asyncio
import logging
import threading
import os
import sys
from datetime import datetime
from typing import Dict, Optional, Any
import datetime as dt

from config import Config
from services.rate_service import RateService

logger = logging.getLogger(__name__)

class InferenceService:
    """実取引データ専用推論実行サービス"""
    
    def __init__(self):
        self.rate_service = RateService()
        self._inference_lock = threading.Lock()
        self._inference_running = False
        
    def is_inference_running(self) -> bool:
        """
        推論が実行中かどうかを確認
        """
        with self._inference_lock:
            return self._inference_running
    
    def reset_inference_state(self):
        """
        推論状態をリセット
        """
        with self._inference_lock:
            self._inference_running = False
    
    async def run_inference(self, current_balance: Dict[str, float]) -> Dict[str, Any]:
        """
        実際の取引データを使用した推論を実行
        
        Args:
            current_balance: 現在の残高情報
            
        Returns:
            推論結果（推奨取引、市場分析、リスク評価など）
            
        Raises:
            Exception: 推論実行中にエラーが発生した場合
        """
        # 推論状態を設定
        with self._inference_lock:
            if self._inference_running:
                raise RuntimeError("推論が既に実行中です")
            self._inference_running = True
        
        try:
            logger.info("[inference_service] 実取引データ推論を開始します")
            print("[inference_service] run_inference: 市場データ取得前")
            # 現在の市場データを取得
            market_data = await self._fetch_market_data()
            print("[inference_service] run_inference: _execute_real_data_inference呼び出し直前")
            logger.info("[inference_service] _execute_real_data_inference呼び出し直前")
            # 実際の取引データを使用した推論を実行
            inference_result = await self._execute_real_data_inference(
                current_balance=current_balance,
                market_data=market_data
            )
            print("[inference_service] run_inference: _execute_real_data_inference呼び出し直後")
            logger.info("[inference_service] _execute_real_data_inference呼び出し直後")
            # 結果を整形
            formatted_result = self._format_inference_result(
                inference_result, 
                current_balance, 
                market_data
            )
            logger.info("[inference_service] 実取引データ推論が正常に完了しました")
            print("[inference_service] run_inference: 完了")
            return formatted_result
        except Exception as e:
            logger.error(f"[inference_service] 実取引データ推論実行中にエラーが発生: {e}")
            print(f"[inference_service] run_inference: 例外発生: {e}")
            # Slack通知（失敗時）
            try:
                from llm_forex_slack_simulator.slack_client import SlackBotClient
                slack_client = SlackBotClient(slack_bot_path="../forex_slack_bot")
                slack_client.send_inference_results({"error": f"inference_service.run_inference例外: {e}"})
            except Exception as ee:
                logger.error(f"[inference_service] Slack通知失敗: {ee}")
            raise
        finally:
            # 推論状態をリセット
            self.reset_inference_state()
    
    async def _fetch_market_data(self) -> Dict[str, Any]:
        """
        市場データを取得（API呼び出しやrate_serviceを使わず、既に取得済みのデータを返す）
        """
        # ここではダミーの空データを返すか、必要に応じて外部からセットされたデータを返すようにする
        # 実際のprompt作成時にデータが取得されている前提
        return {
            "timestamp": datetime.now().isoformat(),
            "rates": {},
            "trends": {}
        }
    
    async def _execute_real_data_inference(self, current_balance: Dict[str, float], market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        llm_forex_slack_simulator を使用した実取引データ推論実行
        """
        try:
            logger.info("[inference_service] 実取引データによる推論を実行中... (_execute_real_data_inference)")
            print("[inference_service] _execute_real_data_inference: SlackForexSimulator呼び出し直前")
            
            # 必要なモジュールをインポート
            import datetime as dt
            
            # llm_forex_slack_simulatorのパス（実取引データ専用）
            SlackForexSimulator = None
            try:
                simulator_path = os.path.join(os.path.dirname(__file__), '..', '..', 'llm_forex_slack_simulator')
                if not os.path.exists(simulator_path):
                    simulator_path = '/mnt/bigdata/00_students/mattsun_ucl/workspace/forex/llm_forex_slack_simulator'
                
                if os.path.exists(simulator_path):
                    sys.path.insert(0, os.path.abspath(simulator_path))
                    from slack_simulator import SlackForexSimulator
                    logger.info("実取引データ推論モジュールを正常に読み込みました")
                else:
                    raise ImportError("llm_forex_slack_simulator が見つかりません")
                    
            except ImportError as import_error:
                logger.warning(f"実取引データ推論のインポートに失敗: {import_error}")
                return await self._fallback_inference_model(current_balance, market_data)
            
            # 現在時刻を取得
            current_time_utc = dt.datetime.utcnow()
            
            # 出力ディレクトリをintegrate-slack-simulator/llm_real_transaction/data/real_out/{日付時刻}に統一
            base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "llm_real_transaction", "data", "real_out")
            now_str = current_time_utc.strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(base_dir, now_str)
            os.makedirs(output_dir, exist_ok=True)
            logger.info(f"出力ディレクトリ: {output_dir}")
            print("[inference_service] _execute_real_data_inference: SlackForexSimulatorインスタンス化直前")
            simulator = SlackForexSimulator("/mnt/bigdata/00_students/mattsun_ucl/workspace/forex/llm_forex_slack_simulator/config/config.json")
            print("[inference_service] _execute_real_data_inference: run_inference呼び出し直前")
            logger.info("[inference_service] run_inference呼び出し直前 (llm_forex_slack_simulator側)")
            # 推論を実行（現在時刻での推論）
            inference_result = simulator.run_inference(current_time=current_time_utc, output_dir=output_dir)
            print("[inference_service] _execute_real_data_inference: run_inference呼び出し直後")
            logger.info("[inference_service] run_inference呼び出し直後 (llm_forex_slack_simulator側)")
            # 結果を解析
            result = {
                "inference_result": inference_result,
                "output_directory": output_dir,
                "timestamp": current_time_utc,
                "data_source": "real_trading_data"
            }
            logger.info("[inference_service] 実取引データ推論が完了しました (_execute_real_data_inference)")
            print("[inference_service] _execute_real_data_inference: 完了")
            return result
        except Exception as e:
            logger.error(f"[inference_service] 実取引データ推論中にエラー: {e}")
            print(f"[inference_service] _execute_real_data_inference: 例外発生: {e}")
            # Slack通知（失敗時）
            try:
                from llm_forex_slack_simulator.slack_client import SlackBotClient
                slack_client = SlackBotClient(slack_bot_path="../forex_slack_bot")
                slack_client.send_inference_results({"error": f"inference_service._execute_real_data_inference例外: {e}"})
            except Exception as ee:
                logger.error(f"[inference_service] Slack通知失敗: {ee}")
            # フォールバック処理
            return await self._fallback_inference_model(current_balance, market_data)
            return await self._fallback_inference_model(current_balance, market_data)
    
    async def _fallback_inference_model(self, current_balance: Dict[str, float], market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        実取引推論システムが利用できない場合のフォールバック推論
        """
        try:
            logger.info("フォールバック推論モデルを実行中...")
            
            await asyncio.sleep(1)  # 簡単な処理時間シミュレート
            
            # 実取引データベースの簡易分析
            simple_analysis = await self._simple_real_data_analysis(current_balance)
            
            # 簡単な推論ロジック
            mock_result = {
                "model_prediction": {
                    "USDJPY": {
                        "action": "buy" if market_data.get("rates", {}).get("USDJPY", 150) < 170 else "sell",
                        "confidence": 0.5,
                        "predicted_price": market_data.get("rates", {}).get("USDJPY", 150) * 1.01
                    },
                    "EURJPY": {
                        "action": "hold",
                        "confidence": 0.3,
                        "predicted_price": market_data.get("rates", {}).get("EURJPY", 160)
                    }
                },
                "risk_factors": ["実取引推論システム利用不可のためフォールバック推論を実行"],
                "confidence_score": 0.4,
                "simulation_analysis": simple_analysis,
                "data_source": "fallback_analysis"
            }
            
            logger.info("フォールバック推論モデル実行完了")
            return mock_result
            
        except Exception as e:
            logger.error(f"フォールバック推論中にエラー: {e}")
            raise RuntimeError(f"推論モデル実行中にエラーが発生: {e}")
    
    async def _simple_real_data_analysis(self, current_balance: Dict[str, float]) -> str:
        """
        シンプルな実取引データ分析
        """
        try:
            analysis_lines = ["=== 簡易実取引データ分析 ===", ""]
            
            # 残高状況
            total_jpy = current_balance.get("JPY", 0)
            usd_amount = current_balance.get("USD", 0)
            eur_amount = current_balance.get("EUR", 0)
            
            if usd_amount > 0:
                total_jpy += usd_amount * 150  # 概算レート
            if eur_amount > 0:
                total_jpy += eur_amount * 160  # 概算レート
                
            analysis_lines.append(f"現在の総資産価値（概算）: ¥{total_jpy:,.2f}")
            analysis_lines.append("")
            
            # 取引履歴ファイルの簡易チェック
            transaction_log = os.path.join(os.path.dirname(__file__), '..', 'data', 'transaction_log.json')
            if os.path.exists(transaction_log):
                import json
                
                transaction_count = 0
                with open(transaction_log, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            transaction_count += 1
                
                analysis_lines.append(f"総取引記録件数: {transaction_count}")
            else:
                analysis_lines.append("取引履歴ファイルが見つかりません")
            
            analysis_lines.append("")
            analysis_lines.append("注意: 実取引推論システムが利用できないため簡易分析を実行")
            
            return "\n".join(analysis_lines)
            
        except Exception as e:
            logger.error(f"簡易実取引データ分析中にエラー: {e}")
            return f"簡易分析に失敗: {str(e)}"
    
    def _format_inference_result(self, raw_result: Dict[str, Any], 
                               current_balance: Dict[str, float], 
                               market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        推論結果をフォーマット（実取引データ専用）
        """
        try:
            formatted_result = {
                "timestamp": datetime.now().isoformat(),
                "current_balance": current_balance,
                "market_data": market_data,
                "recommended_trades": [],
                "market_analysis": "",
                "risk_assessment": "",
                "data_source": raw_result.get("data_source", "real_trading_data")
            }
            
            # 推論結果から推奨取引を取得
            if "inference_result" in raw_result and isinstance(raw_result["inference_result"], dict):
                inference_data = raw_result["inference_result"]
                
                # 推奨取引の抽出
                if "recommended_actions" in inference_data:
                    formatted_result["recommended_trades"] = inference_data["recommended_actions"]
                elif "analysis_result" in inference_data:
                    # 分析結果から推奨を生成
                    formatted_result["recommended_trades"] = self._extract_recommendations_from_analysis(
                        inference_data["analysis_result"], current_balance
                    )
            
            elif "model_prediction" in raw_result:
                # フォールバック推論の結果から推奨取引を生成
                for pair, prediction in raw_result["model_prediction"].items():
                    if prediction["action"] in ["buy", "sell"] and prediction["confidence"] > 0.4:
                        trade = {
                            "pair": pair,
                            "action": prediction["action"],
                            "rate": prediction.get("predicted_price", 0),
                            "amount": self._calculate_suggested_amount(pair, current_balance, prediction),
                            "confidence": prediction["confidence"],
                            "reasoning": f"実取引データ分析により{prediction['action']}を推奨 (信頼度: {prediction['confidence']*100:.0f}%)"
                        }
                        formatted_result["recommended_trades"].append(trade)
            
            # 市場分析を生成
            if "simulation_analysis" in raw_result:
                formatted_result["market_analysis"] = raw_result["simulation_analysis"]
            else:
                formatted_result["market_analysis"] = self._generate_market_analysis(market_data, raw_result)
            
            # リスク評価を生成
            risk_factors = raw_result.get("risk_factors", [])
            if risk_factors:
                formatted_result["risk_assessment"] = "検出されたリスクファクター:\n• " + "\n• ".join(risk_factors)
            else:
                formatted_result["risk_assessment"] = "実取引データに基づく分析では特筆すべきリスクファクターは検出されていません。"
            
            # 実取引データ特有の情報を追加
            if raw_result.get("data_source") == "real_trading_data":
                formatted_result["real_data_summary"] = "実際の取引記録と残高データを基にした推論結果"
                formatted_result["confidence_boost"] = 0.1  # 実データの場合は信頼度を若干向上
            
            return formatted_result
            
        except Exception as e:
            logger.error(f"推論結果フォーマット中にエラー: {e}")
            raise RuntimeError(f"推論結果の処理に失敗しました: {e}")
    
    def _extract_recommendations_from_analysis(self, analysis_text: str, current_balance: Dict[str, float]) -> list:
        """
        分析テキストから推奨取引を抽出
        """
        recommendations = []
        
        # 簡易的なキーワードマッチング
        lines = analysis_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if '推奨' in line or '推薦' in line:
                # 取引推奨を含む行を解析
                if 'USDJPY' in line:
                    action = 'buy' if ('買' in line or 'BUY' in line) else 'sell' if ('売' in line or 'SELL' in line) else 'hold'
                    if action in ['buy', 'sell']:
                        recommendations.append({
                            "pair": "USDJPY",
                            "action": action,
                            "confidence": 0.8,
                            "reasoning": line,
                            "amount": self._calculate_safe_amount("USD", current_balance)
                        })
                
                elif 'EURJPY' in line:
                    action = 'buy' if ('買' in line or 'BUY' in line) else 'sell' if ('売' in line or 'SELL' in line) else 'hold'
                    if action in ['buy', 'sell']:
                        recommendations.append({
                            "pair": "EURJPY",
                            "action": action,
                            "confidence": 0.8,
                            "reasoning": line,
                            "amount": self._calculate_safe_amount("EUR", current_balance)
                        })
        
        return recommendations
    
    def _calculate_suggested_amount(self, pair: str, balance: Dict[str, float], prediction: Dict[str, Any]) -> float:
        """
        推奨取引金額を計算（実取引データベース）
        """
        base_currency = pair[:3]
        balance_amount = balance.get(base_currency, 0)
        
        # 実取引データを考慮したより保守的なポジションサイジング
        risk_ratio = min(0.05, prediction["confidence"] * 0.1)  # 最大5%（シミュレーションより保守的）
        suggested_amount = balance_amount * risk_ratio
        
        return round(suggested_amount, 2)
    
    def _calculate_safe_amount(self, currency: str, balance: Dict[str, float]) -> float:
        """
        安全な取引金額を計算
        """
        balance_amount = balance.get(currency, 0)
        return round(balance_amount * 0.05, 2)  # 残高の5%
    
    def _generate_market_analysis(self, market_data: Dict[str, Any], raw_result: Dict[str, Any]) -> str:
        """
        市場分析テキストを生成
        """
        analysis_lines = []
        
        analysis_lines.append(f"分析時刻: {market_data.get('timestamp', 'N/A')}")
        analysis_lines.append("")
        
        # データソース情報
        data_source = raw_result.get("data_source", "unknown")
        if data_source == "real_trading_data":
            analysis_lines.append("📊 実際の取引記録を基にした分析")
        elif data_source == "fallback_analysis":
            analysis_lines.append("⚠️ フォールバック分析モード")
        
        analysis_lines.append("")
        
        # レート情報
        if market_data.get("rates"):
            analysis_lines.append("現在のレート:")
            for pair, rate in market_data["rates"].items():
                analysis_lines.append(f"  {pair}: {rate:.2f}")
            analysis_lines.append("")
        
        # 全体的な信頼度
        confidence = raw_result.get("confidence_score", 0) * 100
        analysis_lines.append(f"予測信頼度: {confidence:.0f}%")
        
        return "\n".join(analysis_lines)
