"""
レートサービス - レート取得（外部API連携など）
"""

import asyncio
import logging
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
import json

from config import Config

logger = logging.getLogger(__name__)

class RateService:
    """為替レート取得サービス"""
    
    def __init__(self):
        self._rate_cache = {}
        self._cache_expiry = {}
        self._cache_duration_minutes = 5  # キャッシュ有効期間
        
    async def get_current_rate(self, currency_pair: str) -> Optional[float]:
        """
        指定通貨ペアの現在レートを取得
        
        Args:
            currency_pair: 通貨ペア（例: USDJPY）
            
        Returns:
            現在のレート、取得できない場合はNone
        """
        try:
            # キャッシュをチェック
            cached_rate = self._get_cached_rate(currency_pair)
            if cached_rate is not None:
                return cached_rate
            
            # 外部APIからレートを取得
            rate = await self._fetch_rate_from_api(currency_pair)
            
            if rate is not None:
                # キャッシュに保存
                self._cache_rate(currency_pair, rate)
                return rate
            
            # APIが失敗した場合、フォールバックレートを使用
            fallback_rate = self._get_fallback_rate(currency_pair)
            if fallback_rate is not None:
                logger.warning(f"{currency_pair}のAPIレート取得に失敗、フォールバックレートを使用: {fallback_rate}")
                return fallback_rate
            
            logger.error(f"{currency_pair}のレート取得に完全に失敗しました")
            return None
            
        except Exception as e:
            logger.error(f"レート取得中にエラー: {e}")
            return None
    
    async def get_rate_trend(self, currency_pair: str, hours: int = 24) -> Optional[str]:
        """
        指定通貨ペアのトレンド分析を取得
        
        Args:
            currency_pair: 通貨ペア
            hours: 分析対象期間（時間）
            
        Returns:
            トレンド情報（"上昇", "下降", "横ばい"）
        """
        try:
            # TODO: 実際のトレンド分析APIを実装
            # 現在はモックデータを返す
            
            historical_rates = await self._fetch_historical_rates(currency_pair, hours)
            if not historical_rates:
                return None
            
            # 簡単なトレンド分析
            if len(historical_rates) < 2:
                return "横ばい"
            
            start_rate = historical_rates[0]
            end_rate = historical_rates[-1]
            change_percent = ((end_rate - start_rate) / start_rate) * 100
            
            if change_percent > 0.5:
                return "上昇"
            elif change_percent < -0.5:
                return "下降"
            else:
                return "横ばい"
                
        except Exception as e:
            logger.error(f"トレンド分析中にエラー: {e}")
            return None
    
    async def get_multiple_rates(self, currency_pairs: List[str]) -> Dict[str, Optional[float]]:
        """
        複数の通貨ペアのレートを一括取得
        """
        results = {}
        
        # 並行してレートを取得
        tasks = []
        for pair in currency_pairs:
            task = asyncio.create_task(self.get_current_rate(pair))
            tasks.append((pair, task))
        
        for pair, task in tasks:
            try:
                rate = await task
                results[pair] = rate
            except Exception as e:
                logger.error(f"{pair}のレート取得でエラー: {e}")
                results[pair] = None
        
        return results
    
    def _get_cached_rate(self, currency_pair: str) -> Optional[float]:
        """
        キャッシュからレートを取得
        """
        if currency_pair not in self._rate_cache:
            return None
        
        expiry_time = self._cache_expiry.get(currency_pair)
        if expiry_time is None or datetime.now() > expiry_time:
            # キャッシュが期限切れ
            self._rate_cache.pop(currency_pair, None)
            self._cache_expiry.pop(currency_pair, None)
            return None
        
        return self._rate_cache[currency_pair]
    
    def _cache_rate(self, currency_pair: str, rate: float):
        """
        レートをキャッシュに保存
        """
        self._rate_cache[currency_pair] = rate
        self._cache_expiry[currency_pair] = datetime.now() + timedelta(minutes=self._cache_duration_minutes)
    
    async def _fetch_rate_from_api(self, currency_pair: str) -> Optional[float]:
        """
        llm_forex_simulatorのfetch_forex_technicalsを使ってレートを取得
        """
        try:
            import importlib.util
            import sys
            from datetime import datetime
            # fetch.pyのパス
            fetch_path = "/mnt/bigdata/00_students/mattsun_ucl/workspace/forex/llm_forex_simulator/forex_simulator/script/fetch.py"
            spec = importlib.util.spec_from_file_location("fetch_module", fetch_path)
            fetch_module = importlib.util.module_from_spec(spec)
            sys.modules["fetch_module"] = fetch_module
            spec.loader.exec_module(fetch_module)

            # 通貨ペアをyfinance形式に変換（例: USDJPY -> USDJPY=X）
            if not currency_pair.endswith("=X"):
                symbol = currency_pair + "=X"
            else:
                symbol = currency_pair
            now = datetime.now()
            # fetch_forex_technicalsでデータ取得
            result = fetch_module.fetch_forex_technicals(symbol, now, save_to_file=False)
            # 最新のhourlyデータのcloseを取得
            hourly = result.get("hourly", [])
            if hourly and isinstance(hourly, list):
                latest = hourly[0]
                close = latest.get("close")
                if close:
                    return float(close)
            logger.warning(f"llm_forex_simulatorから{currency_pair}のレート取得に失敗")
            return None
        except Exception as e:
            logger.error(f"llm_forex_simulator経由のレート取得でエラー: {e}")
            return None
    
    async def _fetch_historical_rates(self, currency_pair: str, hours: int) -> Optional[List[float]]:
        """
        過去のレートデータを取得
        
        TODO: 実際の履歴データAPIを実装
        """
        try:
            # モックデータを返す
            current_rate = await self.get_current_rate(currency_pair)
            if current_rate is None:
                return None
            
            # 簡単な模擬履歴データ
            import random
            historical_rates = []
            base_rate = current_rate
            
            for i in range(hours):
                # ランダムな変動を追加
                variation = random.uniform(-0.02, 0.02)  # ±2%の変動
                rate = base_rate * (1 + variation)
                historical_rates.append(rate)
                base_rate = rate
            
            return historical_rates
            
        except Exception as e:
            logger.error(f"履歴データ取得中にエラー: {e}")
            return None
    
    def _get_fallback_rate(self, currency_pair: str) -> Optional[float]:
        """
        フォールバックレートを取得（固定値）
        実際の運用では、より信頼性の高いソースを使用
        """
        fallback_rates = {
            "USDJPY": 150.0,
            "EURJPY": 165.0,
            "GBPJPY": 190.0,
            "AUDJPY": 100.0,
            "CHFJPY": 170.0,
            "CADJPY": 110.0,
            "EURUSD": 1.10,
            "GBPUSD": 1.27,
            "AUDUSD": 0.67,
            "USDCHF": 0.88,
            "USDCAD": 1.36,
        }
        
        return fallback_rates.get(currency_pair)
    
    def clear_cache(self):
        """
        レートキャッシュをクリア
        """
        self._rate_cache.clear()
        self._cache_expiry.clear()
        logger.info("レートキャッシュをクリアしました")
    
    def get_cache_status(self) -> Dict[str, Any]:
        """
        キャッシュ状況を取得
        """
        status = {
            "cached_pairs": list(self._rate_cache.keys()),
            "cache_count": len(self._rate_cache),
            "cache_expiry_times": {}
        }
        
        for pair, expiry in self._cache_expiry.items():
            remaining = expiry - datetime.now()
            status["cache_expiry_times"][pair] = {
                "expires_at": expiry.isoformat(),
                "remaining_seconds": max(0, int(remaining.total_seconds()))
            }
        
        return status