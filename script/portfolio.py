from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import json
import os
import datetime
import pandas as pd
import yfinance as yf
import time

@dataclass
class Portfolio:
    """複数通貨の資産を管理するクラス"""

    # 各通貨の残高を辞書で管理 (例: {"JPY": 1000000, "USD": 1000, "EUR": 500})
    balances: Dict[str, float] = field(default_factory=dict)
    # 取引履歴
    trades: List[Dict] = field(default_factory=list)
    # ログファイルのパス - この行を追加
    log_file: str = "forex_trades.jsonl"
    # スプレッド設定 - この行を追加
    spread_config: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        for currency in ["JPY", "USD", "EUR"]:
            
            if currency not in self.balances:
                self.balances[currency] = 0.0
        
        # 既存のログファイルがあれば読み込む
        if os.path.exists(self.log_file):
            self.load_trades_from_log()
            
        # デフォルトのスプレッド設定
        if not self.spread_config:
            self.spread_config = {
                "USDJPY": 0.15,  # 0.15円
                "EURJPY": 0.15,  # 0.15円
                "EURUSD": 0.0018,  # 0.0018ドル
                "default": 0.1   # デフォルト: 0.1%
            }
            
    def load_trades_from_log(self):
        """ログファイルから取引履歴を読み込む"""
        if not os.path.exists(self.log_file):
            return
        
        self.trades = []
        try:
            with open(self.log_file, "r") as f:
                for line in f:
                    if line.strip():  # 空行をスキップ
                        trade = json.loads(line)
                        self.trades.append(trade)
        except Exception as e:
            print(f"ログファイルの読み込みエラー: {e}")

    def get_trades_as_dataframe(self):
        """取引履歴をDataFrameとして取得"""
        if not self.trades:
            return pd.DataFrame()
        
        return pd.DataFrame(self.trades)

    def execute_trade(
        self,
        base_currency: str,
        quote_currency: str,
        amount: float,
        rate: float,
        allow_partial: bool = False
    ):
        """
        通貨ペアの取引を実行

        Args:
            base_currency: 基本通貨 (例: "USD" in USDJPY)
            quote_currency: 相手通貨 (例: "JPY" in USDJPY)
            amount: 基本通貨の量（正=買い、負=売り）
            rate: 為替レート (例: 150.0 for USDJPY)
            allow_partial: 残高不足時に可能な限り取引する場合はTrue
        """
        if amount > 0:
            print(f">>>> 取引実行: [buy] {base_currency}で{quote_currency}を購入, 量: {amount}, レート: {rate} (スプレッド適用済み) 限界取引：{allow_partial}")
        else:
            print(f">>>> 取引実行: [sell] {base_currency}を{quote_currency}で買い戻し, 量: {-amount}, レート: {rate} (スプレッド適用済み) 限界取引：{allow_partial}")
            
        if amount > 0:  # 買い注文（基本通貨を買う）
            required_quote = amount * rate
            available_quote = self.balances[quote_currency]
            if available_quote < required_quote:
                if allow_partial and available_quote > 0:
                    # 買える最大量に調整
                    amount = available_quote / rate
                    required_quote = available_quote
                else:
                    print(f"取引エラー: {quote_currency}の残高が不足しています。必要: {required_quote}, 残高: {available_quote}")
                    return
                    # raise ValueError(f"{quote_currency}の残高が不足しています。必要: {required_quote}, 残高: {available_quote}")
            self.balances[base_currency] += amount
            self.balances[quote_currency] -= required_quote
        else:  # 売り注文（基本通貨を売る）
            amount_abs = abs(amount)
            available_base = self.balances[base_currency]
            if available_base < amount_abs:
                if allow_partial and available_base > 0:
                    amount_abs = available_base
                    amount = -amount_abs
                else:
                    print(f"取引エラー: {base_currency}の残高が不足しています。必要: {amount_abs}, 残高: {available_base}")
                    return
                    # raise ValueError(f"{base_currency}の残高が不足しています。必要: {amount_abs}, 残高: {available_base}")
            self.balances[base_currency] -= amount_abs
            self.balances[quote_currency] += amount_abs * rate

        # 取引履歴に追加
        self.trades.append({
            "base_currency": base_currency,
            "quote_currency": quote_currency,
            "amount": amount,
            "rate": rate,
            "type": "buy" if amount > 0 else "sell"
        })
    
    def trade_by_pair(self, currency_pair: str, amount: float, rate: float, allow_partial: bool = False):
        """
        通貨ペア表記での取引を実行
        
        Args:
            currency_pair: 通貨ペア (例: "USDJPY")
            amount: 取引量（正=買い、負=売り）
            rate: 為替レート
        """
        # 通貨ペアから基本通貨と相手通貨を抽出
        if len(currency_pair) != 6:
            raise ValueError("通貨ペアは6文字である必要があります (例: USDJPY)")
        
        base_currency = currency_pair[:3]
        quote_currency = currency_pair[3:]
        
        self.execute_trade(base_currency, quote_currency, amount, rate, allow_partial=allow_partial)
        
    
    def get_total_value(self, base_currency: str, rates: Dict[str, float]) -> float:
        """
        特定の通貨単位での総資産価値を計算
        
        Args:
            base_currency: 基準通貨 (例: "JPY")
            rates: 為替レートの辞書 {通貨ペア: レート}
                  例: {"USDJPY": 150.0, "EURJPY": 160.0}
        
        Returns:
            float: 基準通貨での総資産価値
        """
        total = self.balances.get(base_currency, 0)
        
        for currency, amount in self.balances.items():
            if currency == base_currency:
                continue  # 基準通貨はそのまま
            
            # 通貨ペアを構築して適切なレートを取得
            currency_pair = f"{currency}{base_currency}"
            reverse_pair = f"{base_currency}{currency}"
            
            if currency_pair in rates:
                # 直接のレートがある場合 (例: USDJPY)
                total += amount * rates[currency_pair]
            elif reverse_pair in rates:
                # 逆レートがある場合 (例: JPYUSD)
                total += amount / rates[reverse_pair]
            else:
                raise ValueError(f"通貨 {currency} から {base_currency} への変換レートがありません")
                
        return total
    
    def summary(self, rates: Dict[str, float], base_currency: str = "JPY") -> Dict:
        """
        ポートフォリオの概要を取得
        
        Args:
            rates: 為替レートの辞書
            base_currency: 基準通貨（デフォルト: "JPY"）
        
        Returns:
            Dict: ポートフォリオの概要情報
        """
        # 各通貨の価値を基準通貨で計算
        values = {}
        for currency, amount in self.balances.items():
            if currency == base_currency:
                values[currency] = amount
            else:
                # 通貨ペアを構築
                currency_pair = f"{currency}{base_currency}"
                reverse_pair = f"{base_currency}{currency}"
                
                if currency_pair in rates:
                    values[currency] = amount * rates[currency_pair]
                elif reverse_pair in rates:
                    values[currency] = amount / rates[reverse_pair]
                else:
                    values[currency] = None  # レートがない場合
        
        return {
            "balances": dict(self.balances),
            "values_in_base": values,
            "total_value": self.get_total_value(base_currency, rates),
            "base_currency": base_currency,
            "trades_count": len(self.trades)
        }
    
    def to_json(self) -> str:
        """ポートフォリオ情報をJSON形式で出力"""
        return json.dumps({
            "balances": self.balances,
            "trades": self.trades
        }, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str):
        """JSON形式からポートフォリオを復元"""
        data = json.loads(json_str)
        portfolio = cls(balances=data.get("balances", {}))
        portfolio.trades = data.get("trades", [])
        return portfolio

    def get_current_rates(
        self,
        currency_pairs=None,
        current_time: datetime.datetime | None = None,
    ) -> Dict[str, float] | None:

        """
        指定された通貨ペアの現在のレートをYFinanceから取得
        交差レート計算機能付き
        
        Args:
            currency_pairs: 通貨ペアのリスト（デフォルトはUSDJPY, EURJPY, EURUSD）
        
        Returns:
            Dict[str, float] | None: 通貨ペアとレートのマッピング。取得できなかった場合はNone
        """
        if currency_pairs is None:
            currency_pairs = ["EURUSD", "USDJPY", "EURJPY"]

        if current_time is None:
            current_time = datetime.datetime.now()

        # JST assumed if naive
        if current_time.tzinfo is None:
            current_time_utc = current_time - datetime.timedelta(hours=9)
        else:
            current_time_utc = current_time.astimezone(datetime.timezone.utc).replace(tzinfo=None)

        start = current_time_utc - datetime.timedelta(days=1)
        end = current_time_utc
        
        # 通貨ペアの=Xを追加（YFinance形式に変換）
        formatted_pairs = []
        for pair in currency_pairs:
            if not pair.endswith("=X"):
                formatted_pairs.append(f"{pair}=X")
            else:
                formatted_pairs.append(pair)
        
        try:
            rates = {}
            for i in range(5):  # 最大5回リトライ
                # YFinanceからデータを取得
                data = yf.download(
                    formatted_pairs,
                    start=start,
                    end=end,
                    interval="1m",
                    group_by="ticker",
                    progress=False,
                )

                rates.clear()

                for pair in formatted_pairs:
                    clean_pair = pair.replace("=X", "")
                    try:
                        # 最新のClose価格を取得
                        if len(data) > 0:
                            if isinstance(data, pd.DataFrame) and pair in data:
                                latest_price = data[pair]["Close"].iloc[-1]
                            else:
                                latest_price = data[(pair, "Close")].iloc[-1]
                            if pd.notna(latest_price):
                                rates[clean_pair] = float(latest_price)
                            else:
                                print(f"警告: {pair}の最新価格がNaNです")
                        else:
                            print(f"警告: {pair}のデータがありません")
                    except Exception as e:
                        print(f"エラー: {pair}のデータ取得に失敗しました: {e}")

                # 交差レート計算
                if (
                    ("EURUSD" not in rates or pd.isna(rates.get("EURUSD")))
                    and "EURJPY" in rates
                    and "USDJPY" in rates
                    and pd.notna(rates["USDJPY"])
                    and rates["USDJPY"] != 0
                ):
                    rates["EURUSD"] = rates["EURJPY"] / rates["USDJPY"]
                    print(
                        f"EURUSD: 交差レートで計算しました → {rates['EURUSD']:.6f}"
                    )

                if (
                    ("EURJPY" not in rates or pd.isna(rates.get("EURJPY")))
                    and "EURUSD" in rates
                    and "USDJPY" in rates
                    and pd.notna(rates["EURUSD"])
                ):
                    rates["EURJPY"] = rates["EURUSD"] * rates["USDJPY"]
                    print(
                        f"EURJPY: 交差レートで計算しました → {rates['EURJPY']:.4f}"
                    )

                if (
                    ("USDJPY" not in rates or pd.isna(rates.get("USDJPY")))
                    and "EURJPY" in rates
                    and "EURUSD" in rates
                    and pd.notna(rates["EURUSD"])
                    and rates["EURUSD"] != 0
                ):
                    rates["USDJPY"] = rates["EURJPY"] / rates["EURUSD"]
                    print(
                        f"USDJPY: 交差レートで計算しました → {rates['USDJPY']:.4f}"
                    )

                missing = [
                    pair
                    for pair in currency_pairs
                    if pair not in rates or pd.isna(rates[pair])
                ]
                if not missing:
                    return rates

                print(
                    f"警告: {', '.join(missing)}のレートが取得できませんでした、リトライします ({i+1}/5回目)"
                )
                time.sleep(2)  # 2秒待機してから再試行

            # 最終的に全てのレートが揃わなかった場合は失敗とみなす
            return None

        except Exception as e:
            print(f"レート取得エラー: {e}")
            return {}
    
    def apply_spread(self, rate: float, currency_pair: str, is_buy: bool) -> float:
        """
        銀行のスプレッド（手数料）を考慮したレートを計算
        
        Args:
            rate: 基本レート
            currency_pair: 通貨ペア===
            is_buy: True=買い注文（ASKレート）, False=売り注文（BIDレート）
            
        Returns:
            float: スプレッド適用後のレート
        """
        # 通貨ペアごとのスプレッド設定を取得
        spread = self.spread_config.get(currency_pair, None)
        
        # 通貨ペア固有の設定がない場合はデフォルトのパーセンテージを使用
        if spread is None:
            spread = rate * (self.spread_config.get("default", 0.001))
        
        # 買いと売りでレート調整
        if is_buy:
            # 買い注文ではレートが高くなる（不利になる）
            return rate + spread
        else:
            # 売り注文ではレートが低くなる（不利になる）
            return rate - spread
    
    def execute_trade_with_spread(self, base_currency: str, quote_currency: str, amount: float):
        """
        現在のレートとスプレッドを適用して取引を実行
        
        Args:
            base_currency: 基本通貨 (例: "USD" in USDJPY)
            quote_currency: 相手通貨 (例: "JPY" in USDJPY)
            amount: 基本通貨の量（正=買い、負=売り）
        """
        # 通貨ペアを構築
        currency_pair = f"{base_currency}{quote_currency}"
        
        # 現在のレートを取得
        rates = self.get_current_rates([currency_pair])
        if currency_pair not in rates:
            raise ValueError(f"通貨ペア {currency_pair} のレートを取得できませんでした")
        
        base_rate = rates[currency_pair]
        
        # スプレッド適用済みのレート計算
        is_buy = amount > 0
        effective_rate = self.apply_spread(base_rate, currency_pair, is_buy)
        
        # 実際の取引を実行
        self.execute_trade(base_currency, quote_currency, amount, effective_rate)
        
        return effective_rate
    
    def trade_by_pair_with_spread(self, currency_pair: str, amount: float):
        """
        通貨ペア表記でスプレッド適用済みの取引を実行
        
        Args:
            currency_pair: 通貨ペア (例: "USDJPY")
            amount: 取引量（正=買い、負=売り）
        """
        # 通貨ペアから基本通貨と相手通貨を抽出
        if len(currency_pair) != 6:
            raise ValueError("通貨ペアは6文字である必要があります (例: USDJPY)")
        
        base_currency = currency_pair[:3]
        quote_currency = currency_pair[3:]
        
        return self.execute_trade_with_spread(base_currency, quote_currency, amount)
    
    def get_market_data_summary(self, current_time: datetime.datetime | None = None) -> Dict | None:

        """
        現在の市場データと自分のポートフォリオ情報をまとめて取得
        
        Returns:
            Dict | None: 市場データとポートフォリオの概要。レート取得に失敗した場合はNone
        """
        # 主要通貨ペアのレートを取得
        market_rates = self.get_current_rates(current_time=current_time)
        if market_rates is None:
            return None

        # スプレッド適用済みのレートを計算
        bank_rates = {
            pair: {
                "buy_rate": self.apply_spread(rate, pair, True),
                "sell_rate": self.apply_spread(rate, pair, False),
                "market_rate": rate,
                "buy_spread": self.apply_spread(rate, pair, True) - rate,
                "sell_spread": rate - self.apply_spread(rate, pair, False)
            } 
            for pair, rate in market_rates.items()
        }
        
        # JPYでの総資産を計算
        total_jpy = None
        if "USDJPY" in market_rates and "EURJPY" in market_rates:
            total_jpy = self.get_total_value("JPY", market_rates)
        
        # 市場データとポートフォリオ情報をまとめる
        if current_time is None:
            current_time = datetime.datetime.now()

        return {
            "timestamp": current_time.isoformat(),
            "market_rates": market_rates,
            "bank_rates": bank_rates,
            "portfolio": {
                "balances": dict(self.balances),
                "total_jpy": total_jpy,
                "trades_count": len(self.trades)
            }
        }
    
    def display_market_info(
        self, current_time: datetime.datetime | None = None
    ) -> tuple[str, pd.DataFrame | None]:
        """現在の市場情報とポートフォリオ状況を表示"""
        market_data = self.get_market_data_summary(current_time)
        if market_data is None:
            print("レート取得に失敗したため、市場情報を表示できません")
            return "", None
        
        # 取引履歴の詳細を整形
        # trades = self.trades if hasattr(self, "trades") else []
        # if trades:
        #     trades_text = "【取引履歴】\n" + "\n".join(
        #     f"{i+1}. {t['type'].upper()} {t['amount']:,.2f} {t['base_currency']} @ {t['rate']:.4f} ({t['base_currency']}/{t['quote_currency']})"
        #     for i, t in enumerate(trades)
        #     )
        # else:
        #     trades_text = "【取引履歴】\n  取引履歴なし"

        market_info_text = (
            "=" * 50 + "\n"
            f"市場情報 - {market_data['timestamp']}\n"
            + "=" * 50 + "\n\n"
            "【為替レート】\n"
            + "\n".join(
            f"{pair}:\n"
            f"  市場レート: {rates['market_rate']:.4f}\n"
            f"  銀行買値(Ask): {rates['buy_rate']:.4f} (スプレッド: +{rates['buy_spread']:.4f})\n"
            f"  銀行売値(Bid): {rates['sell_rate']:.4f} (スプレッド: -{rates['sell_spread']:.4f})"
            for pair, rates in market_data['bank_rates'].items()
            ) + "\n\n"
        )
        print(market_info_text)
        
        # 各通貨ペアごとの現在のレート情報をリスト化
        pair_current_rates = [
            {
            "pair": pair,
            "market_rate": rates["market_rate"],
            "buy_rate": rates["buy_rate"],
            "sell_rate": rates["sell_rate"],
            "buy_spread": rates["buy_spread"],
            "sell_spread": rates["sell_spread"]
            }
            for pair, rates in market_data['bank_rates'].items()
        ]
        # pandas DataFrameに変換
        pair_current_rates = pd.DataFrame(pair_current_rates)
        
        
        return market_info_text, pair_current_rates
    
    def set_spread_config(self, config: Dict[str, float]):
        """銀行のスプレッド（手数料）設定を更新"""
        self.spread_config.update(config)
        
    

# 使用例
if __name__ == "__main__":
    # 初期ポートフォリオの作成（100万円、1000ドル、0ユーロ）
    portfolio = Portfolio(balances={"JPY": 100000, "USD": 0, "EUR": 0}, log_file="example_trades.jsonl")
    
    # # スプレッド設定をカスタマイズ
    # portfolio.set_spread_config({
    #     "USDJPY": 0.30,   # より大きなスプレッド
    #     "EURJPY": 0.40,
    #     "EURUSD": 0.0005
    # })
    
    # 現在の市場情報を表示
    portfolio.display_market_info()
    
    try:
        # 現在のレートとスプレッドを使用して取引
        buy_rate = portfolio.trade_by_pair_with_spread("USDJPY", 500)
        print(f"\nUSDJPYを500ドル分購入しました（レート: {buy_rate:.4f}）")
        
        # 更新された市場情報を表示
        # portfolio.display_market_info()
    except Exception as e:
        print(f"取引エラー: {e}")
    
    # 取引履歴をDataFrameで取得して表示
    trades_df = portfolio.get_trades_as_dataframe()
    print("\n取引履歴:")
    print(trades_df)
    
# else :
    # print("このスクリプトは直接実行されていません。モジュールとしてインポートされました。")
    # portfolio = Portfolio(balances={"JPY": 100000, "USD": 0, "EUR": 0}, log_file="trades.jsonl")