"""
残高マネージャ - 残高の読み込み/書き込み
"""

import json
import logging
import os
import threading
from typing import Dict
from datetime import datetime

from config import Config

logger = logging.getLogger(__name__)

class BalanceManager:
    """残高管理クラス"""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._ensure_data_directory()
        self._ensure_balance_file()
    
    def get_balance(self) -> Dict[str, float]:
        """
        現在の残高を取得
        
        Returns:
            通貨別残高の辞書
        """
        with self._lock:
            try:
                if not os.path.exists(Config.BALANCE_FILE):
                    return self._get_initial_balance()
                
                with open(Config.BALANCE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # データの妥当性チェック
                if not isinstance(data, dict):
                    logger.warning("残高ファイルの形式が無効です。初期残高を返します。")
                    return self._get_initial_balance()
                
                # 新形式（'balances'キーあり）と旧形式（直接通貨データ）の両方に対応
                if 'balances' in data:
                    balances = data['balances']
                else:
                    # 旧形式の場合、'last_updated'等のメタデータを除外して通貨データのみ取得
                    balances = {k: v for k, v in data.items() 
                              if k in Config.SUPPORTED_CURRENCIES or k.upper() in Config.SUPPORTED_CURRENCIES}
                
                # サポート対象通貨が全て含まれているかチェック
                for currency in Config.SUPPORTED_CURRENCIES:
                    if currency not in balances:
                        balances[currency] = Config.INITIAL_BALANCE_JPY if currency == "JPY" else 0.0
                
                return balances
                
            except (json.JSONDecodeError, FileNotFoundError) as e:
                logger.error(f"残高ファイル読み込み中にエラー: {e}")
                return self._get_initial_balance()
            except Exception as e:
                logger.error(f"残高取得中に予期しないエラー: {e}")
                return self._get_initial_balance()
    
    def update_balance(self, new_balance: Dict[str, float]) -> bool:
        """
        残高を更新
        
        Args:
            new_balance: 新しい残高データ
            
        Returns:
            更新成功の場合True
        """
        with self._lock:
            try:
                # バリデーション
                if not self._validate_balance_data(new_balance):
                    logger.error("無効な残高データです")
                    return False
                
                # バックアップを作成
                self._create_backup()
                
                # 残高データを準備
                balance_data = {
                    "balances": new_balance,
                    "last_updated": datetime.now().isoformat(),
                    "version": "1.0"
                }
                
                # ファイルに書き込み
                with open(Config.BALANCE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(balance_data, f, indent=2, ensure_ascii=False)
                
                logger.info("残高を正常に更新しました")
                return True
                
            except Exception as e:
                logger.error(f"残高更新中にエラー: {e}")
                
                # バックアップから復元を試行
                try:
                    self._restore_from_backup()
                    logger.info("バックアップから残高を復元しました")
                except Exception as backup_error:
                    logger.error(f"バックアップからの復元に失敗: {backup_error}")
                
                return False
    
    def get_balance_history(self, limit: int = 10) -> list:
        """
        残高変更履歴を取得
        
        Args:
            limit: 取得する履歴数の上限
            
        Returns:
            残高変更履歴のリスト
        """
        try:
            history_file = Config.BALANCE_FILE.replace('.json', '_history.json')
            
            if not os.path.exists(history_file):
                return []
            
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            
            # 最新のものから指定件数を取得
            return history[-limit:] if isinstance(history, list) else []
            
        except Exception as e:
            logger.error(f"残高履歴取得中にエラー: {e}")
            return []
    
    def _ensure_data_directory(self):
        """
        データディレクトリの存在を確認・作成
        """
        Config.create_data_directory()
    
    def _ensure_balance_file(self):
        """
        残高ファイルの存在を確認・作成
        """
        if not os.path.exists(Config.BALANCE_FILE):
            initial_balance = self._get_initial_balance()
            self.update_balance(initial_balance)
            logger.info("初期残高ファイルを作成しました")
    
    def _get_initial_balance(self) -> Dict[str, float]:
        """
        初期残高を取得
        """
        initial_balance = {}
        
        for currency in Config.SUPPORTED_CURRENCIES:
            if currency == "JPY":
                initial_balance[currency] = Config.INITIAL_BALANCE_JPY
            else:
                initial_balance[currency] = 0.0
        
        return initial_balance
    
    def _validate_balance_data(self, balance: Dict[str, float]) -> bool:
        """
        残高データの妥当性をチェック
        """
        if not isinstance(balance, dict):
            return False
        
        for currency, amount in balance.items():
            # 通貨コードの妥当性チェック
            if not isinstance(currency, str) or len(currency) != 3:
                logger.warning(f"無効な通貨コード: {currency}")
                return False
            
            # 金額の妥当性チェック
            if not isinstance(amount, (int, float)):
                logger.warning(f"無効な金額: {currency}={amount}")
                return False
            
            # 負の残高チェック（一部の通貨では許可する場合もある）
            if amount < -1000000:  # 極端な負の値は無効
                logger.warning(f"極端な負の残高: {currency}={amount}")
                return False
        
        return True
    
    def _create_backup(self):
        """
        現在の残高ファイルのバックアップを integrate-slack-simulator/llm_real_transaction/data/balance/past_data/{日時}.json に保存
        """
        try:
            if os.path.exists(Config.BALANCE_FILE):
                backup_dir = os.path.join(os.path.dirname(Config.BALANCE_FILE), '../../data/balance/past_data')
                backup_dir = os.path.abspath(backup_dir)
                os.makedirs(backup_dir, exist_ok=True)
                backup_file = os.path.join(backup_dir, f'{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
                with open(Config.BALANCE_FILE, 'r', encoding='utf-8') as src:
                    with open(backup_file, 'w', encoding='utf-8') as dst:
                        dst.write(src.read())
                self._cleanup_old_backups(backup_dir)
        except Exception as e:
            logger.warning(f"バックアップ作成中にエラー: {e}")

    def _restore_from_backup(self):
        """
        最新の integrate-slack-simulator/llm_real_transaction/data/balance/past_data/{日時}.json から残高を復元
        """
        backup_dir = os.path.join(os.path.dirname(Config.BALANCE_FILE), '../../data/balance/past_data')
        backup_dir = os.path.abspath(backup_dir)
        import glob
        backup_files = glob.glob(os.path.join(backup_dir, '*.json'))
        if not backup_files:
            raise FileNotFoundError("バックアップファイルが見つかりません")
        latest_backup = max(backup_files, key=os.path.getmtime)
        with open(latest_backup, 'r', encoding='utf-8') as src:
            with open(Config.BALANCE_FILE, 'w', encoding='utf-8') as dst:
                dst.write(src.read())

    def _cleanup_old_backups(self, backup_dir, keep_count: int = 5):
        """
        古いバックアップファイルを削除（最新5件まで保持）
        """
        try:
            import glob
            backup_files = glob.glob(os.path.join(backup_dir, '*.json'))
            if len(backup_files) <= keep_count:
                return
            backup_files.sort(key=os.path.getmtime)
            files_to_delete = backup_files[:-keep_count]
            for file_path in files_to_delete:
                os.remove(file_path)
                logger.debug(f"古いバックアップファイルを削除: {file_path}")
        except Exception as e:
            logger.warning(f"バックアップファイル整理中にエラー: {e}")
    
    def _save_balance_history(self, balance: Dict[str, float]):
        """
        残高変更履歴を保存
        """
        try:
            history_file = Config.BALANCE_FILE.replace('.json', '_history.json')
            
            # 既存の履歴を読み込み
            history = []
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            
            # 新しい履歴エントリを追加
            history_entry = {
                "timestamp": datetime.now().isoformat(),
                "balances": balance.copy()
            }
            history.append(history_entry)
            
            # 履歴数を制限（最新100件まで）
            if len(history) > 100:
                history = history[-100:]
            
            # 履歴ファイルに保存
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.warning(f"残高履歴保存中にエラー: {e}")
    
    def reset_to_initial_balance(self) -> bool:
        """
        残高を初期状態にリセット
        """
        try:
            initial_balance = self._get_initial_balance()
            success = self.update_balance(initial_balance)
            
            if success:
                logger.info("残高を初期状態にリセットしました")
            else:
                logger.error("残高リセットに失敗しました")
            
            return success
            
        except Exception as e:
            logger.error(f"残高リセット中にエラー: {e}")
            return False