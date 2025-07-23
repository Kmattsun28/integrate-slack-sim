import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import requests
# こちらに変更
from script.fetch import fetch_forex_technicals_with_news
from script.handle_transaction_log import print_asset_summary
# ニュース取得設定
NEWS_HOURS_BACK = 12  # 過去何時間のニュースを取得するか
NEWS_API_LIMIT = 10   # API から取得する最大件数
NEWS_DISPLAY_LIMIT = 5  # プロンプトに表示する最大件数（個別通貨・通貨ペア用）
NEWS_COMBINED_LIMIT = 5  # プロンプトに表示する最大件数（統合セクション用）

# global 
# symbol, latest_6, latest_3d, latest_macd, latest_signal = None, None, None, None, None, None, None
def normalize_forex_symbol(symbol):
    """通貨ペアのシンボルをYFinance形式に正規化する"""
    # スラッシュを削除
    symbol = symbol.replace('/', '')
    # =Xがなければ追加
    if not symbol.endswith('=X'):
        symbol += '=X'
    return symbol


def extract_currencies_from_symbol(symbol):
    """
    通貨ペアシンボルから通貨を抽出する
    
    Args:
        symbol (str): 通貨ペアシンボル (例: "USDJPY=X", "EUR/JPY", "EURUSD")
    
    Returns:
        list: 通貨のリスト (例: ["USD", "JPY"])
    """
    # 正規化：スラッシュと=Xを削除
    clean_symbol = symbol.replace('/', '').replace('=X', '').upper()
    
    # 通貨ペアから個別通貨を抽出
    if len(clean_symbol) == 6:
        base_currency = clean_symbol[:3]
        quote_currency = clean_symbol[3:]
        return [base_currency, quote_currency]
    else:
        # フォールバック：主要通貨を返す
        return ["USD", "JPY", "EUR"]


def generate_news_section(symbols, all_news):
    """
    ニュース専用セクションを生成する関数。
    prompt_idea.txtの形式に合わせて、通貨別・通貨ペア別にニュースを分類。

    Args:
        symbols (list): 通貨ペアのリスト。
        all_news (dict): 各通貨ペアのニュースデータ。

    Returns:
        str: ニュース専用セクションのプロンプト。
    """
    prompt = "各通貨関連ニュース\n"
    prompt += "\n"
    
    # 各通貨ペアから個別通貨を抽出
    individual_currencies = set()
    for symbol in symbols:
        currencies = extract_currencies_from_symbol(symbol)
        individual_currencies.update(currencies)
    
    # 個別通貨のニュースセクション
    for currency in sorted(individual_currencies):
        prompt += f"[{currency}]:\n"
        # 各通貨に関連するニュースを収集
        currency_news = []
        for symbol in symbols:
            symbol_currencies = extract_currencies_from_symbol(symbol)
            if currency in symbol_currencies:
                news_list = all_news.get(symbol, [])
                currency_news.extend(news_list)
        
        if currency_news:
            # 重複を除去し、公開日時でソート
            seen_titles = set()
            unique_news = []
            for news in currency_news:
                title = news.get("title", "")
                if title not in seen_titles:
                    seen_titles.add(title)
                    unique_news.append(news)
            
            # 最新のニュースを最初に表示
            unique_news.sort(key=lambda x: x.get("published", ""), reverse=True)
            
            for news in unique_news[:NEWS_DISPLAY_LIMIT]:  # 設定可能な件数まで
                published = news.get("published", "")
                title = news.get("title", "")
                summary = news.get("summary", "")
                prompt += f"- {published} {title}: {summary}\n"
        else:
            prompt += "- 関連ニュースなし\n"
        prompt += "\n"
    
    # 通貨ペアのニュースセクション
    for symbol in symbols:
        symbol_clean = symbol.replace("=X", "")
        formatted_pair = f"{symbol_clean[:3]}/{symbol_clean[3:]}"
        prompt += f"[{formatted_pair}]:\n"
        
        news_list = all_news.get(symbol, [])
        if news_list:
            for news in news_list[:NEWS_DISPLAY_LIMIT]:  # 設定可能な件数まで
                published = news.get("published", "")
                title = news.get("title", "")
                summary = news.get("summary", "")
                prompt += f"- {published} {title}: {summary}\n"
        else:
            prompt += "- 関連ニュースなし\n"
        prompt += "\n"
    
    # 全通貨統合セクション（例: USD/JPY/EUR）
    all_currencies = "/".join(sorted(individual_currencies))
    prompt += f"[{all_currencies}]:\n"
    
    # 複数通貨に関連するニュースのみを抽出
    multi_currency_news = []
    
    # 全てのニュースを調べて、複数の通貨に関連するものを見つける
    all_news_items = []
    for news_list in all_news.values():
        all_news_items.extend(news_list)
    
    # 重複除去
    seen_titles = set()
    unique_news_items = []
    for news in all_news_items:
        title = news.get("title", "")
        if title not in seen_titles:
            seen_titles.add(title)
            unique_news_items.append(news)
    
    # 複数通貨に関連するニュースを特定
    for news in unique_news_items:
        title = news.get("title", "").upper()
        summary = news.get("summary", "").upper()
        content = f"{title} {summary}"
        
        # 個別通貨が何個含まれているかをカウント
        currency_count = 0
        for currency in individual_currencies:
            if currency in content:
                currency_count += 1
        
        # 通貨ペアが含まれているかもチェック
        pair_found = False
        for symbol in symbols:
            clean_symbol = symbol.replace("=X", "").replace("/", "")
            if clean_symbol.upper() in content:
                pair_found = True
                break
        
        # 複数通貨に関連している、または通貨ペアが明示的に言及されている場合のみ追加
        if currency_count >= 2 or pair_found:
            multi_currency_news.append(news)
    
    if multi_currency_news:
        # 公開日時でソート
        multi_currency_news.sort(key=lambda x: x.get("published", ""), reverse=True)
        
        for news in multi_currency_news[:NEWS_COMBINED_LIMIT]:  # 設定可能な件数まで
            published = news.get("published", "")
            title = news.get("title", "")
            summary = news.get("summary", "")
            prompt += f"- {published} {title}: {summary}\n"
    else:
        prompt += "- 関連ニュースなし\n"
    
    prompt += "\n"
    return prompt


def generate_news_section_fixed(symbols, pair_news, individual_currency_news):
    """
    ニュース専用セクションを生成する関数（修正版）。
    個別通貨のニュースと通貨ペアのニュースを明確に分離。

    Args:
        symbols (list): 通貨ペアのリスト。
        pair_news (dict): 各通貨ペアのニュースデータ。
        individual_currency_news (dict): 各個別通貨のニュースデータ。

    Returns:
        str: ニュース専用セクションのプロンプト。
    """
    prompt = "各通貨関連ニュース\n"
    prompt += "\n"
    
    # 各通貨ペアから個別通貨を抽出
    individual_currencies = set()
    for symbol in symbols:
        currencies = extract_currencies_from_symbol(symbol)
        individual_currencies.update(currencies)
    
    # 個別通貨のニュースセクション（専用取得したニュースを使用）
    for currency in sorted(individual_currencies):
        prompt += f"[{currency}]:\n"
        
        currency_news = individual_currency_news.get(currency, [])
        
        if currency_news:
            # 最新のニュースを最初に表示
            sorted_news = sorted(currency_news, key=lambda x: x.get("published", ""), reverse=True)
            
            for news in sorted_news[:NEWS_DISPLAY_LIMIT]:  # 設定可能な件数まで
                published = news.get("published", "")
                title = news.get("title", "")
                summary = news.get("summary", "")
                prompt += f"- {published} {title}: {summary}\n"
        else:
            prompt += "- 関連ニュースなし\n"
        prompt += "\n"
    
    # 通貨ペアのニュースセクション
    for symbol in symbols:
        symbol_clean = symbol.replace("=X", "")
        formatted_pair = f"{symbol_clean[:3]}/{symbol_clean[3:]}"
        prompt += f"[{formatted_pair}]:\n"
        
        news_list = pair_news.get(symbol, [])
        if news_list:
            for news in news_list[:NEWS_DISPLAY_LIMIT]:  # 設定可能な件数まで
                published = news.get("published", "")
                title = news.get("title", "")
                summary = news.get("summary", "")
                prompt += f"- {published} {title}: {summary}\n"
        else:
            prompt += "- 関連ニュースなし\n"
        prompt += "\n"
    
    # 全通貨統合セクション（例: USD/JPY/EUR）
    all_currencies = "/".join(sorted(individual_currencies))
    prompt += f"[{all_currencies}]:\n"
    
    # 複数通貨に関連するニュースのみを抽出
    multi_currency_news = []
    
    # 全てのニュースを調べて、複数の通貨に関連するものを見つける
    all_news_items = []
    for news_list in individual_currency_news.values():
        all_news_items.extend(news_list)
    for news_list in pair_news.values():
        all_news_items.extend(news_list)
    
    # 重複除去
    seen_titles = set()
    unique_news_items = []
    for news in all_news_items:
        title = news.get("title", "")
        if title not in seen_titles:
            seen_titles.add(title)
            unique_news_items.append(news)
    
    # 複数通貨に関連するニュースを特定
    for news in unique_news_items:
        title = news.get("title", "").upper()
        summary = news.get("summary", "").upper()
        content = f"{title} {summary}"
        
        # 個別通貨が何個含まれているかをカウント
        currency_count = 0
        for currency in individual_currencies:
            if currency in content:
                currency_count += 1
        
        # 通貨ペアが含まれているかもチェック
        pair_found = False
        for symbol in symbols:
            clean_symbol = symbol.replace("=X", "").replace("/", "")
            if clean_symbol.upper() in content:
                pair_found = True
                break
        
        # 複数通貨に関連している、または通貨ペアが明示的に言及されている場合のみ追加
        if currency_count >= 2 or pair_found:
            multi_currency_news.append(news)
    
    if multi_currency_news:
        # 公開日時でソート
        multi_currency_news.sort(key=lambda x: x.get("published", ""), reverse=True)
        
        for news in multi_currency_news[:NEWS_COMBINED_LIMIT]:  # 設定可能な件数まで
            published = news.get("published", "")
            title = news.get("title", "")
            summary = news.get("summary", "")
            prompt += f"- {published} {title}: {summary}\n"
    else:
        prompt += "- 関連ニュースなし\n"

    prompt += "\n"
    return prompt

def create_prompt(
    current_time_utc: str,
    symbols: list,
    portfolio,
    currencies: list = None,
    transaction_file: str = 'transaction_log.json'
) -> str:
    
    """
    Create a prompt for the LLM based on the provided data and strategy.
    
    Args:
        current_time_utc: 現在時刻（UTC）
        symbols: 通貨ペアのリスト
        portfolio: ポートフォリオインスタンス
        currencies: ニュースフィルター用の通貨リスト (例: ["USD", "JPY", "EUR"])
        
    Returns:
        prompt: 生成されたプロンプト文字列
        pair_current_rates: 現在の通貨レート情報
    """
    if isinstance(current_time_utc, str):
        current_time_utc = datetime.strptime(current_time_utc, "%Y-%m-%d %H:%M:%S")
    elif isinstance(current_time_utc, datetime):
        pass  # そのまま使用
    else:
        # その他の型の場合は文字列に変換してからパース
        current_time_utc = datetime.strptime(str(current_time_utc), "%Y-%m-%d %H:%M:%S")
        
    # datetime オブジェクトのまま計算して保持（UTC → JST変換）
    current_time_jst = current_time_utc + timedelta(hours=9)
    prompt = ""
    all_news = {}
    individual_currency_news = {}

    # Step 1: 各通貨ペアのテクニカル指標とニュースを取得
    for symbol in symbols:
        # 通貨ペアの正規化
        normalized_symbol = normalize_forex_symbol(symbol)
        
        # 通貨ペアごとに適切な通貨フィルターを設定
        # 各通貨ペアから個別に通貨を抽出してフィルターとして使用
        symbol_currencies = extract_currencies_from_symbol(symbol)
        
        # Fetch technical indicators and news with currency filter
        # テクニカル指標はJST時刻、ニュースはUTC時刻で取得する
        data = fetch_forex_technicals_with_news(
            normalized_symbol, 
            current_time_jst,  # テクニカル指標用（JST）
            news_base_time=current_time_utc,  # ニュース用（UTC）
            hours_back=NEWS_HOURS_BACK,
            limit=NEWS_API_LIMIT,
            currencies=symbol_currencies,
            save_to_file=False,
            use_cache=True  # キャッシュを有効化
        )

        # 技術分析データをプロンプトに追加（ニュースは除く）
        prompt += data_2_prompt(normalized_symbol, data)
        prompt += f"\n==============================================\n"

        # ニュースデータを収集（通貨ペア専用）
        all_news[symbol] = data.get("news", [])

    # Step 2: 個別通貨のニュースを専用取得
    individual_currencies = set()
    for symbol in symbols:
        currencies = extract_currencies_from_symbol(symbol)
        individual_currencies.update(currencies)
    
    for currency in individual_currencies:
        # 個別通貨のニュースを専用取得
        try:
            # 単一通貨でニュースを取得
            currency_data = fetch_forex_technicals_with_news(
                "USDJPY=X",  # ダミーシンボル（テクニカル指標は使わない）
                current_time_jst,  # テクニカル指標用（JST）
                news_base_time=current_time_utc,  # ニュース用（UTC）
                hours_back=NEWS_HOURS_BACK,
                limit=NEWS_API_LIMIT,
                currencies=[currency],  # 単一通貨のみ指定
                save_to_file=False,
                use_cache=True  # キャッシュを有効化
            )
            individual_currency_news[currency] = currency_data.get("news", [])
        except Exception as e:
            print(f"Warning: 通貨 {currency} のニュース取得でエラー: {e}")
            individual_currency_news[currency] = []

    # ニュース専用セクションを追加
    prompt += generate_news_section_fixed(symbols, all_news, individual_currency_news)
    

    # 市場情報を追加
    add_prompt, pair_current_rates = portfolio.display_market_info(current_time_jst)
    if pair_current_rates is None:
        return "", None
    prompt += add_prompt
    
    # 取引ログを追加
    prompt += f"\n==================================================\n"
    prompt += f"取引情報"
    prompt += f"\n==================================================\n"
    
    prompt += print_asset_summary(transaction_file, current_rates=pair_current_rates)

    prompt += f"\n==================================================\n"


    # 質問セクションを追加
    prompt += """
以上の情報をもとに、次の質問に答えてください。

Q: あなたは資産を増やすためにどの通貨ペアをいくら買う、売りますか？ ただし、変動率が小さいと予測される場合は「Hold」とし、【ポートフォリオ】の資産残高を参照し資産内で運用してください。

回答は次のcsv形式の例に従う形で記述して下さい。購入しない場合は記述する必要はありません。
例:
行動,通貨ペア,数量
BUY,USDJPY,1000 (例)
SELL,EURJPY,500 (例)

行動,通貨ペア,数量

"""

    return prompt, pair_current_rates



# ============================================================

def data_2_prompt(symbol, data):
    """
    特定の時間と通貨ペアのデータを取得し、LLM向けのプロンプトを生成する関数
    
    Args:
        symbols (list): 通貨ペアのリスト（例: ["USDJPY=X"]）
        
    Returns:
        str: 生成されたプロンプトテキスト
    """
    
    # 通貨ペアの取得と整形
    symbol_clean = data["meta"]["symbol"].replace("=X", "")
    base_time = data["meta"]["base_time_jst"]
    
    # プロンプトの構築開始
    prompt = f"""[通貨ペア]: {symbol_clean[:3]}/{symbol_clean[3:]}

[現在の日時]
{base_time.replace('-', '/')}

[直近6時間（1時間足）の価格とRSIの推移]:
"""

    # 時間足データの追加（最新のデータを先頭に）
    for i, hour_data in enumerate(reversed(data["hourly"]), 1):
        prompt += f"{i}時間前: 始値: {hour_data['open']:.4f}, 終値: {hour_data['close']:.4f}, RSI: {hour_data['rsi_14']:.1f}\n"
    
    # RSIの解釈を追加
#     prompt += """
# ※RSIの解釈:
# - RSI > 70: 買われすぎ（反転下落の可能性）
# - RSI < 30: 売られすぎ（反転上昇の可能性）
# - RSIの方向性: 上昇/下降トレンドの強さを示す
# """
    
    # 日足データの追加
    prompt += f"\n[直近{len(data['daily'])}日間（日足）の価格と移動平均]:\n"
    for day_data in data["daily"]:
        date_str = day_data["date"]
        prompt += f"{date_str}: 始値: {day_data['open']:.4f}, 終値: {day_data['close']:.4f}, SMA(20): {day_data['sma_20']:.4f}\n"
    
    # 移動平均線の解釈を追加
#     prompt += """
# ※SMA(20)の解釈:
# - 価格 > SMA(20): 上昇トレンドの可能性
# - 価格 < SMA(20): 下降トレンドの可能性
# - SMA傾斜: 上向きなら強気、下向きなら弱気
# """
    
    # インジケーターの追加
    prompt += f"\n[MACD（現在）]: MACD: {data['indicators']['macd']:.4f}, Signal: {data['indicators']['macd_signal']:.4f}\n"
    
    # MACDの解釈を追加
#     prompt += """
# ※MACDの解釈:
# - MACD > シグナル: 買いシグナル
# - MACD < シグナル: 売りシグナル
# - MACDがゼロラインを上回る: 強気相場
# - MACDがゼロラインを下回る: 弱気相場
# """
    
    return prompt

if __name__ == "__main__":
    # テスト用のデータを作成
    from script.portfolio import Portfolio
    
    symbols = ["USDJPY=X","EURJPY=X", "EURUSD=X"]
    current_time_utc = datetime.utcnow()
    
    # テスト用ポートフォリオを作成
    test_portfolio = Portfolio(balances={"JPY": 100000, "USD": 0, "EUR": 0})
    
    # プロンプトを生成
    prompt, pair_current_rates = create_prompt(current_time_utc, symbols, test_portfolio)
    
    # 結果を表示
    print(prompt)