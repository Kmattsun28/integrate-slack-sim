"""
取引ログ - 取引ログの読み込み/書き込み
"""

import json
import logging
import os
import threading
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from config import Config

logger = logging.getLogger(__name__)

class TransactionLog:
    """取引ログ管理クラス"""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._ensure_data_directory()
        self._ensure_log_file()
    
    def add_transaction(self, transaction: Dict[str, Any]) -> str:
        """
        取引をログに追加
        
        Args:
            transaction: 取引データ
            
        Returns:
            追加された取引のID
        """
        with self._lock:
            try:
                # 取引にIDとタイムスタンプを追加
                transaction_id = str(uuid.uuid4())
                transaction["id"] = transaction_id
                
                if "timestamp" not in transaction:
                    transaction["timestamp"] = datetime.now().isoformat()
                
                # 既存のログを読み込み
                logs = self._load_logs()
                
                # 新しい取引を追加
                logs.append(transaction)
                
                # ログファイルに保存
                self._save_logs(logs)
                
                logger.info(f"取引ログを追加しました: {transaction_id}")
                return transaction_id
                
            except Exception as e:
                logger.error(f"取引ログ追加中にエラー: {e}")
                raise
    
    def get_logs(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        取引ログを取得
        
        Args:
            limit: 取得する件数の上限
            
        Returns:
            取引ログのリスト（新しい順）
        """
        try:
            logs = self._load_logs()
            
            # 新しい順にソート
            logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            if limit:
                logs = logs[:limit]
            
            return logs
            
        except Exception as e:
            logger.error(f"取引ログ取得中にエラー: {e}")
            return []
    
    def get_last_transaction(self) -> Optional[Dict[str, Any]]:
        """
        最新の取引を取得
        """
        try:
            logs = self._load_logs()
            
            if not logs:
                return None
            
            # 最新の取引を取得（取り消し済みは除く）
            for log in reversed(logs):
                if log.get("type") == "取引" and log.get("status") != "取り消し済み":
                    return log
            
            return None
            
        except Exception as e:
            logger.error(f"最新取引取得中にエラー: {e}")
            return None
    
    def get_last_undo_transaction(self) -> Optional[Dict[str, Any]]:
        """
        最新の取り消し取引を取得
        """
        try:
            logs = self._load_logs()
            
            if not logs:
                return None
            
            # 最新の取り消し取引を取得
            for log in reversed(logs):
                if log.get("type") == "取り消し":
                    return log
            
            return None
            
        except Exception as e:
            logger.error(f"最新取り消し取引取得中にエラー: {e}")
            return None
    
    def get_transaction_by_id(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """
        IDで取引を取得
        """
        try:
            logs = self._load_logs()
            
            for log in logs:
                if log.get("id") == transaction_id:
                    return log
            
            return None
            
        except Exception as e:
            logger.error(f"取引ID検索中にエラー: {e}")
            return None
    
    def mark_transaction_undone(self, transaction_id: str) -> bool:
        """
        取引を取り消し済みにマーク
        """
        with self._lock:
            try:
                logs = self._load_logs()
                
                for log in logs:
                    if log.get("id") == transaction_id:
                        log["status"] = "取り消し済み"
                        log["undone_at"] = datetime.now().isoformat()
                        break
                else:
                    logger.warning(f"取引ID {transaction_id} が見つかりません")
                    return False
                
                self._save_logs(logs)
                logger.info(f"取引 {transaction_id} を取り消し済みにマークしました")
                return True
                
            except Exception as e:
                logger.error(f"取引マーク中にエラー: {e}")
                return False
    
    def get_user_transactions(self, user_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        特定ユーザーの取引ログを取得
        """
        try:
            all_logs = self._load_logs()
            
            # ユーザーIDでフィルター
            user_logs = [log for log in all_logs if log.get("user_id") == user_id]
            
            # 新しい順にソート
            user_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            if limit:
                user_logs = user_logs[:limit]
            
            return user_logs
            
        except Exception as e:
            logger.error(f"ユーザー取引ログ取得中にエラー: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        取引統計を取得
        """
        try:
            logs = self._load_logs()
            
            stats = {
                "total_transactions": 0,
                "completed_transactions": 0,
                "undone_transactions": 0,
                "currency_pairs": set(),
                "transaction_types": {},
                "date_range": {
                    "earliest": None,
                    "latest": None
                }
            }
            
            for log in logs:
                stats["total_transactions"] += 1
                
                # ステータス別カウント
                status = log.get("status", "")
                if status == "完了":
                    stats["completed_transactions"] += 1
                elif status == "取り消し済み":
                    stats["undone_transactions"] += 1
                
                # 通貨ペア集計
                pair = log.get("currency_pair", "")
                if pair and pair != "":
                    stats["currency_pairs"].add(pair)
                
                # 取引タイプ集計
                trans_type = log.get("type", "その他")
                stats["transaction_types"][trans_type] = stats["transaction_types"].get(trans_type, 0) + 1
                
                # 日付範囲
                timestamp = log.get("timestamp")
                if timestamp:
                    if stats["date_range"]["earliest"] is None or timestamp < stats["date_range"]["earliest"]:
                        stats["date_range"]["earliest"] = timestamp
                    if stats["date_range"]["latest"] is None or timestamp > stats["date_range"]["latest"]:
                        stats["date_range"]["latest"] = timestamp
            
            # setをlistに変換
            stats["currency_pairs"] = list(stats["currency_pairs"])
            
            return stats
            
        except Exception as e:
            logger.error(f"統計取得中にエラー: {e}")
            return {}
    
    def get_recent_transactions(self, limit: int = 10, hours: int = None) -> List[Dict[str, Any]]:
        """
        最近の取引を取得
        
        Args:
            limit: 取得する最大件数（デフォルト: 10）
            hours: 過去何時間以内の取引を取得するか（Noneの場合は全期間）
            
        Returns:
            取引リスト（新しい順）
        """
        try:
            logs = self._load_logs()
            
            if not logs:
                return []
            
            # 時間範囲でフィルタリング（指定された場合）
            if hours is not None:
                cutoff_time = datetime.now() - timedelta(hours=hours)
                cutoff_iso = cutoff_time.isoformat()
                
                logs = [log for log in logs 
                       if log.get("timestamp", "") >= cutoff_iso]
            
            # タイムスタンプで降順ソート（新しい順）
            logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            # 指定件数まで取得
            return logs[:limit]
            
        except Exception as e:
            logger.error(f"最近の取引取得中にエラー: {e}")
            return []

    def _load_logs(self) -> List[Dict[str, Any]]:
        """
        ログファイルからデータを読み込み
        """
        try:
            if not os.path.exists(Config.TRANSACTION_LOG_FILE):
                return []
            
            with open(Config.TRANSACTION_LOG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, dict) and "transactions" in data:
                return data["transactions"]
            elif isinstance(data, list):
                return data
            else:
                logger.warning("取引ログファイルの形式が無効です")
                return []
                
        except json.JSONDecodeError as e:
            logger.error(f"取引ログファイルのJSON解析エラー: {e}")
            return []
        except Exception as e:
            logger.error(f"取引ログ読み込み中にエラー: {e}")
            return []
    
    def _save_logs(self, logs: List[Dict[str, Any]]):
        """
        ログファイルにデータを保存
        """
        try:
            # バックアップを作成
            self._create_backup()
            
            log_data = {
                "transactions": logs,
                "last_updated": datetime.now().isoformat(),
                "version": "1.0",
                "total_count": len(logs)
            }
            
            with open(Config.TRANSACTION_LOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"取引ログ保存中にエラー: {e}")
            raise
    
    def _ensure_data_directory(self):
        """
        データディレクトリの存在を確認・作成
        """
        Config.create_data_directory()
    
    def _ensure_log_file(self):
        """
        ログファイルの存在を確認・作成
        """
        if not os.path.exists(Config.TRANSACTION_LOG_FILE):
            self._save_logs([])
            logger.info("取引ログファイルを作成しました")
    
    def _create_backup(self):
        """
        現在のログファイルのバックアップを integrate-slack-simulator/llm_real_transaction/data/log/past_data/{日時}.json に保存
        """
        try:
            if os.path.exists(Config.TRANSACTION_LOG_FILE):
                backup_dir = os.path.join(os.path.dirname(Config.TRANSACTION_LOG_FILE), '../../data/log/past_data')
                backup_dir = os.path.abspath(backup_dir)
                os.makedirs(backup_dir, exist_ok=True)
                backup_file = os.path.join(backup_dir, f'{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
                with open(Config.TRANSACTION_LOG_FILE, 'r', encoding='utf-8') as src:
                    with open(backup_file, 'w', encoding='utf-8') as dst:
                        dst.write(src.read())
                self._cleanup_old_backups(backup_dir)
        except Exception as e:
            logger.warning(f"ログバックアップ作成中にエラー: {e}")

    def _restore_from_backup(self):
        """
        最新の integrate-slack-simulator/llm_real_transaction/data/log/past_data/{日時}.json からログを復元
        """
        backup_dir = os.path.join(os.path.dirname(Config.TRANSACTION_LOG_FILE), '../../data/log/past_data')
        backup_dir = os.path.abspath(backup_dir)
        import glob
        backup_files = glob.glob(os.path.join(backup_dir, '*.json'))
        if not backup_files:
            raise FileNotFoundError("ログバックアップファイルが見つかりません")
        latest_backup = max(backup_files, key=os.path.getmtime)
        with open(latest_backup, 'r', encoding='utf-8') as src:
            with open(Config.TRANSACTION_LOG_FILE, 'w', encoding='utf-8') as dst:
                dst.write(src.read())

    def _cleanup_old_backups(self, backup_dir, keep_count: int = 10):
        """
        古いログバックアップファイルを削除（最新10件まで保持）
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
                logger.debug(f"古いログバックアップファイルを削除: {file_path}")
        except Exception as e:
            logger.warning(f"ログバックアップファイル整理中にエラー: {e}")
    
    def clear_logs(self) -> bool:
        """
        全ての取引ログを削除
        """
        with self._lock:
            try:
                # バックアップを作成
                self._create_backup()
                
                # ログをクリア
                self._save_logs([])
                
                logger.info("取引ログをクリアしました")
                return True
                
            except Exception as e:
                logger.error(f"取引ログクリア中にエラー: {e}")
                return False
    
    def export_logs(self, file_path: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> bool:
        """
        取引ログをファイルにエクスポート
        """
        try:
            logs = self._load_logs()
            
            # 日付でフィルター
            if start_date or end_date:
                filtered_logs = []
                for log in logs:
                    timestamp = log.get("timestamp", "")
                    if start_date and timestamp < start_date:
                        continue
                    if end_date and timestamp > end_date:
                        continue
                    filtered_logs.append(log)
                logs = filtered_logs
            
            export_data = {
                "exported_at": datetime.now().isoformat(),
                "date_range": {
                    "start": start_date,
                    "end": end_date
                },
                "total_count": len(logs),
                "transactions": logs
            }
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"取引ログを {file_path} にエクスポートしました")
            return True
            
        except Exception as e:
            logger.error(f"取引ログエクスポート中にエラー: {e}")
            return False