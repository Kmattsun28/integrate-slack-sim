"""
取引サービス - 取引ロジック、残高更新、取引ログ管理
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from models.balance_manager import BalanceManager
from models.transaction_log import TransactionLog
from config import Config

logger = logging.getLogger(__name__)

class TradingService:
    """取引実行サービス"""
    
    def __init__(self):
        self.balance_manager = BalanceManager()
        self.transaction_log = TransactionLog()
        
    def get_current_balance(self) -> Dict[str, float]:
        """
        現在の残高を取得
        """
        return self.balance_manager.get_balance()
    
    def get_transaction_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        取引ログを取得
        """
        return self.transaction_log.get_logs(limit=limit)
    
    async def execute_trade(self, currency_pair: str, amount: float, rate: float, user_id: str) -> Dict[str, Any]:
        """
        取引を実行
        
        Args:
            currency_pair: 通貨ペア（例: USDJPY）
            amount: 取引金額（正の値で買い、負の値で売り）
            rate: 取引レート
            user_id: 実行ユーザーID
            
        Returns:
            取引結果
        """
        try:
            logger.info(f"取引実行: {currency_pair}, {amount}, {rate}, user: {user_id}")
            
            # 通貨ペアの妥当性チェック
            if not self._validate_currency_pair(currency_pair):
                return {
                    "success": False,
                    "error": f"サポートされていない通貨ペアです: {currency_pair}"
                }
            
            # 金額の妥当性チェック
            if amount == 0:
                return {
                    "success": False,
                    "error": "取引金額が0です"
                }
            
            # レートの妥当性チェック
            if rate <= 0:
                return {
                    "success": False,
                    "error": "無効なレートです"
                }
            
            # 現在の残高を取得
            current_balance = self.balance_manager.get_balance()
            
            # 取引可能性をチェック
            validation_result = self._validate_trade(current_balance, currency_pair, amount, rate)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": validation_result["error"]
                }
            
            # 取引を実行
            new_balance = self._execute_trade_logic(current_balance, currency_pair, amount, rate)
            
            # 残高を更新
            self.balance_manager.update_balance(new_balance)
            
            # 取引ログに記録
            self.transaction_log.add_transaction({
                "timestamp": datetime.now().isoformat(),
                "currency_pair": currency_pair,
                "amount": amount,
                "rate": rate,
                "user_id": user_id,
                "type": "取引",
                "status": "完了"
            })
            
            logger.info("取引が正常に完了しました")
            
            return {
                "success": True,
                "new_balance": new_balance,
                "transaction_details": {
                    "pair": currency_pair,
                    "amount": amount,
                    "rate": rate
                }
            }
            
        except Exception as e:
            logger.error(f"取引実行中にエラー: {e}")
            return {
                "success": False,
                "error": f"取引実行中にエラーが発生しました: {str(e)}"
            }
    
    async def undo_last_transaction(self, user_id: str) -> Dict[str, Any]:
        """
        最新の取引を取り消し
        """
        try:
            # 最新の取引を取得
            last_transaction = self.transaction_log.get_last_transaction()
            if not last_transaction:
                return {
                    "success": False,
                    "error": "取り消す取引がありません"
                }
            
            if last_transaction.get("status") == "取り消し済み":
                return {
                    "success": False,
                    "error": "この取引は既に取り消されています"
                }
            
            # 逆取引を実行
            reverse_amount = -last_transaction["amount"]
            current_balance = self.balance_manager.get_balance()
            new_balance = self._execute_trade_logic(
                current_balance,
                last_transaction["currency_pair"],
                reverse_amount,
                last_transaction["rate"]
            )
            
            # 残高を更新
            self.balance_manager.update_balance(new_balance)
            
            # 元の取引を取り消し済みにマーク
            self.transaction_log.mark_transaction_undone(last_transaction["id"])
            
            # 取り消しログを追加
            self.transaction_log.add_transaction({
                "timestamp": datetime.now().isoformat(),
                "currency_pair": last_transaction["currency_pair"],
                "amount": reverse_amount,
                "rate": last_transaction["rate"],
                "user_id": user_id,
                "type": "取り消し",
                "status": "完了",
                "original_transaction_id": last_transaction["id"]
            })
            
            return {
                "success": True,
                "new_balance": new_balance,
                "undone_transaction": self._format_transaction_summary(last_transaction)
            }
            
        except Exception as e:
            logger.error(f"取引取り消し中にエラー: {e}")
            return {
                "success": False,
                "error": f"取引取り消し中にエラーが発生しました: {str(e)}"
            }
    
    async def redo_last_transaction(self, user_id: str) -> Dict[str, Any]:
        """
        取り消した取引をやり直し
        """
        try:
            # 最新の取り消し取引を取得
            last_undo = self.transaction_log.get_last_undo_transaction()
            if not last_undo:
                return {
                    "success": False,
                    "error": "やり直す取引がありません"
                }
            
            # 元の取引情報を取得
            original_transaction = self.transaction_log.get_transaction_by_id(
                last_undo["original_transaction_id"]
            )
            
            if not original_transaction:
                return {
                    "success": False,
                    "error": "元の取引情報が見つかりません"
                }
            
            # 元の取引を再実行
            current_balance = self.balance_manager.get_balance()
            new_balance = self._execute_trade_logic(
                current_balance,
                original_transaction["currency_pair"],
                original_transaction["amount"],
                original_transaction["rate"]
            )
            
            # 残高を更新
            self.balance_manager.update_balance(new_balance)
            
            # やり直しログを追加
            self.transaction_log.add_transaction({
                "timestamp": datetime.now().isoformat(),
                "currency_pair": original_transaction["currency_pair"],
                "amount": original_transaction["amount"],
                "rate": original_transaction["rate"],
                "user_id": user_id,
                "type": "やり直し",
                "status": "完了",
                "original_transaction_id": original_transaction["id"]
            })
            
            return {
                "success": True,
                "new_balance": new_balance,
                "redone_transaction": self._format_transaction_summary(original_transaction)
            }
            
        except Exception as e:
            logger.error(f"取引やり直し中にエラー: {e}")
            return {
                "success": False,
                "error": f"取引やり直し中にエラーが発生しました: {str(e)}"
            }
    
    async def override_balance(self, currency: str, new_amount: float, user_id: str) -> Dict[str, Any]:
        """
        残高を上書き
        """
        try:
            current_balance = self.balance_manager.get_balance()
            old_amount = current_balance.get(currency, 0)
            
            # 新しい残高を設定
            current_balance[currency] = new_amount
            self.balance_manager.update_balance(current_balance)
            
            # 上書きログを追加
            self.transaction_log.add_transaction({
                "timestamp": datetime.now().isoformat(),
                "currency_pair": f"{currency}/OVERRIDE",
                "amount": new_amount - old_amount,
                "rate": 1.0,
                "user_id": user_id,
                "type": "残高上書き",
                "status": "完了",
                "details": f"{currency}: {old_amount} -> {new_amount}"
            })
            
            return {
                "success": True,
                "new_balance": current_balance,
                "override_details": {
                    "currency": currency,
                    "old_amount": old_amount,
                    "new_amount": new_amount
                }
            }
            
        except Exception as e:
            logger.error(f"残高上書き中にエラー: {e}")
            return {
                "success": False,
                "error": f"残高上書き中にエラーが発生しました: {str(e)}"
            }
    
    def _validate_currency_pair(self, currency_pair: str) -> bool:
        """
        通貨ペアの妥当性をチェック
        """
        if len(currency_pair) != 6:
            return False
        
        base_currency = currency_pair[:3]
        quote_currency = currency_pair[3:]
        
        return (base_currency in Config.SUPPORTED_CURRENCIES and 
                quote_currency in Config.SUPPORTED_CURRENCIES)
    
    def _validate_trade(self, balance: Dict[str, float], currency_pair: str, amount: float, rate: float) -> Dict[str, Any]:
        """
        取引可能性をチェック
        """
        base_currency = currency_pair[:3]
        quote_currency = currency_pair[3:]
        
        if amount > 0:  # 買い注文
            # quote_currencyでの支払い能力をチェック
            required_amount = abs(amount) * rate
            available_balance = balance.get(quote_currency, 0)
            
            if available_balance < required_amount:
                return {
                    "valid": False,
                    "error": f"{quote_currency}の残高が不足しています。必要: {required_amount:.2f}, 利用可能: {available_balance:.2f}"
                }
        else:  # 売り注文
            # base_currencyの保有量をチェック
            required_amount = abs(amount)
            available_balance = balance.get(base_currency, 0)
            
            if available_balance < required_amount:
                return {
                    "valid": False,
                    "error": f"{base_currency}の残高が不足しています。必要: {required_amount:.2f}, 利用可能: {available_balance:.2f}"
                }
        
        return {"valid": True}
    
    def _execute_trade_logic(self, balance: Dict[str, float], currency_pair: str, amount: float, rate: float) -> Dict[str, float]:
        """
        取引ロジックを実行し、新しい残高を計算
        """
        new_balance = balance.copy()
        base_currency = currency_pair[:3]
        quote_currency = currency_pair[3:]
        
        if amount > 0:  # 買い注文
            # base_currencyを増加、quote_currencyを減少
            new_balance[base_currency] = new_balance.get(base_currency, 0) + amount
            new_balance[quote_currency] = new_balance.get(quote_currency, 0) - (amount * rate)
        else:  # 売り注文
            # base_currencyを減少、quote_currencyを増加
            new_balance[base_currency] = new_balance.get(base_currency, 0) + amount  # amountは負の値
            new_balance[quote_currency] = new_balance.get(quote_currency, 0) + (abs(amount) * rate)
        
        return new_balance
    
    def _format_transaction_summary(self, transaction: Dict[str, Any]) -> str:
        """
        取引情報を簡潔にフォーマット
        """
        amount_str = f"+{transaction['amount']}" if transaction['amount'] > 0 else str(transaction['amount'])
        return f"{transaction['currency_pair']}: {amount_str} @ {transaction['rate']}"