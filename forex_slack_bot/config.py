"""
設定ファイル - APIキー、チャンネルIDなどの設定管理
"""

import os
from typing import Optional
from dotenv import load_dotenv

# .envファイルを読み込む
load_dotenv()

class Config:
    """アプリケーション設定クラス"""
    
    # Slack関連設定
    SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_SIGNING_SECRET: str = os.getenv("SLACK_SIGNING_SECRET", "")
    SLACK_APP_TOKEN: str = os.getenv("SLACK_APP_TOKEN", "")
    
    # チャンネル設定
    DEFAULT_CHANNEL: str = os.getenv("DEFAULT_CHANNEL", "#forex-trading")
    ADMIN_CHANNEL: str = os.getenv("ADMIN_CHANNEL", "#admin")
    
    # データファイルパス
    DATA_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    BALANCE_FILE: str = os.path.join(DATA_DIR, "balance", "balance.json")
    TRANSACTION_LOG_FILE: str = os.path.join(DATA_DIR, "log", "transaction_log.json")
    
    # 推論結果保存先
    REAL_DATA_OUTPUT_DIR: str = os.path.join(DATA_DIR, "real_out")
    
    # 推論モデル関連設定
    MODEL_PATH: str = os.getenv("MODEL_PATH", "./models")
    GPU_MEMORY_LIMIT_GB: int = int(os.getenv("GPU_MEMORY_LIMIT_GB", "8"))
    INFERENCE_TIMEOUT_SECONDS: int = int(os.getenv("INFERENCE_TIMEOUT_SECONDS", "300"))
    
    # 実データ推論設定
    REAL_DATA_INFERENCE_ENABLED: bool = os.getenv("REAL_DATA_INFERENCE_ENABLED", "true").lower() == "true"
    
    # 定期推論設定
    PERIODIC_INFERENCE_ENABLED: bool = os.getenv("PERIODIC_INFERENCE_ENABLED", "true").lower() == "true"
    PERIODIC_INFERENCE_INTERVAL_HOURS: int = int(os.getenv("PERIODIC_INFERENCE_INTERVAL_HOURS", "1"))
    PERIODIC_INFERENCE_USE_REAL_DATA: bool = os.getenv("PERIODIC_INFERENCE_USE_REAL_DATA", "false").lower() == "true"
    
    # レート取得API設定
    RATE_API_URL: str = os.getenv("RATE_API_URL", "")
    RATE_API_KEY: str = os.getenv("RATE_API_KEY", "")
    
    # 取引設定
    INITIAL_BALANCE_JPY: float = float(os.getenv("INITIAL_BALANCE_JPY", "1000000.0"))
    SUPPORTED_CURRENCIES: list = ["JPY", "USD", "EUR"]
    
    # セキュリティ設定
    ADMIN_USER_IDS: list = os.getenv("ADMIN_USER_IDS", "").split(",") if os.getenv("ADMIN_USER_IDS") else []
    
    # ログ設定
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "forex_bot.log")
    
    @classmethod
    def validate_config(cls) -> bool:
        """設定の妥当性チェック"""
        required_vars = [
            ("SLACK_BOT_TOKEN", cls.SLACK_BOT_TOKEN),
            ("SLACK_SIGNING_SECRET", cls.SLACK_SIGNING_SECRET),
            ("SLACK_APP_TOKEN", cls.SLACK_APP_TOKEN),
        ]
        
        missing_vars = []
        for var_name, var_value in required_vars:
            if not var_value:
                missing_vars.append(var_name)
        
        if missing_vars:
            print(f"以下の環境変数が設定されていません: {', '.join(missing_vars)}")
            return False
        
        return True
    
    @classmethod
    def create_data_directory(cls):
        """データディレクトリが存在しない場合は作成"""
        os.makedirs(cls.DATA_DIR, exist_ok=True)
        
    @classmethod
    def get_summary(cls) -> dict:
        """設定の概要を取得（機密情報は除く）"""
        return {
            "data_dir": cls.DATA_DIR,
            "periodic_inference_enabled": cls.PERIODIC_INFERENCE_ENABLED,
            "periodic_inference_interval_hours": cls.PERIODIC_INFERENCE_INTERVAL_HOURS,
            "supported_currencies": cls.SUPPORTED_CURRENCIES,
            "initial_balance_jpy": cls.INITIAL_BALANCE_JPY,
            "log_level": cls.LOG_LEVEL,
        }