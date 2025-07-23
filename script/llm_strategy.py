from typing import Dict


# def decide_trade(timeseries: Dict, news_summary: str, indicators: Dict) -> str:
#     """LLM を用いて取引指示を決定する"""
#     prompt = (
#         f"Forex data: {timeseries}\n"
#         f"News summary: {news_summary}\n"
#         f"Technical indicators: {indicators}\n"
#         "Based on the above, output a trading decision such as 'BUY USD/JPY 1000'."
#     )
#     # TODO: 実際の LLM API に置き換える
#     return "HOLD"

def extract_decisions(response: str) -> str:
    """LLM のレスポンスから取引指示を抽出する"""
    lines = response.strip().split("\n")
    decisions = []
    for line in lines:
        line_upper = line.upper()
        if line_upper.startswith("BUY") or line_upper.startswith("SELL") or line_upper.startswith("HOLD"):
            try:
                decisions.append(parse_decision(line.strip()))
            except ValueError as e:
                # 不正な形式の行は結果に含めない
                print(f"Decision parse error: {e}")
                continue
    if decisions:
        return decisions
    else:
        return None
    
def parse_decision(decision: str) -> Dict[str, str]:
    """取引指示をパースして辞書形式に変換する"""
    parts = decision.split(",")
    if len(parts) != 3:
        raise ValueError(f"Invalid decision format: {decision}")

    action = parts[0].strip().upper()
    symbol = parts[1].strip()
    quantity = parts[2].strip()

    # 数量は数値である必要がある
    try:
        float(quantity)
    except ValueError:
        raise ValueError(f"Invalid quantity in decision: {decision}")

    
    return {
        "action": action,
        "symbol": symbol,
        "quantity": quantity
    }
    
def do_deal(decisions, pair_current_rates, portfolio):
    """ポートフォリオに対して取引指示を実行する"""
    
    for decision in decisions:
        action = decision.get("action")
        symbol = decision.get("symbol")
        quantity = decision.get("quantity")
        
        symbol = symbol.replace("/", "")  # 6文字にするためにスラッシュを削除
        inv_symbol = None
        if len(symbol) == 6:
            inv_symbol = symbol[3:] + symbol[:3]
        else:
            print(f"Invalid symbol format: {symbol}")
            continue
        
        # check rate
        rate_row = pair_current_rates[pair_current_rates["pair"] == symbol]
        
        # check if rate_row is empty
        if rate_row.empty:
            print(f"Warning: No rate data available for {symbol}. Skipping trade.")
            continue
        # NaNチェック
        if rate_row["buy_rate"].isnull().any() or rate_row["sell_rate"].isnull().any():
            print(f"!!! Warning: NaN rate found for {symbol}. Skipping trade.")
            continue
        
        if action == "BUY":
            quantity = float(quantity)
            rate = rate_row["buy_rate"].iloc[0] if not rate_row.empty else None
            portfolio.trade_by_pair(symbol, quantity, rate, allow_partial=True)
        elif action == "SELL":
            quantity = -float(quantity)
            rate = rate_row["sell_rate"].iloc[0] if not rate_row.empty else None
            portfolio.trade_by_pair(symbol, quantity, rate, allow_partial=True)
        elif action == "HOLD":
            continue
        else:
            print(f"Unknown action: {action}")
