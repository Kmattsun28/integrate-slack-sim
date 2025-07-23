import json
from typing import Dict, List
from datetime import datetime


def calculate_final_assets(transaction_log: Dict, initial_assets: Dict[str, float] ) -> Dict[str, float]:
    """
    transaction_logを読み込んで、初期資産から全ての取引を適用した後の資産を計算する
    
    Args:
        transaction_log (Dict): 取引ログのデータ
        initial_assets (Dict[str, float]): 初期資産 {"JPY": 1000000, "USD": 0, "EUR": 0}
        
    Returns:
        Dict[str, float]: 最終的な資産状況
    """
    # 初期資産をコピー
    assets = initial_assets.copy()
    
    # 各取引を適用
    for transaction in transaction_log["transactions"]:
        currency_pair = transaction["currency_pair"]
        amount = transaction["amount"]
        rate = transaction["rate"]
        
        # 通貨ペア取得
        base_currency = currency_pair[:3]
        quote_currency = currency_pair[3:]
        
        # 基軸通貨と対象通貨が辞書に存在しない場合は初期化
        if base_currency not in assets:
            assets[base_currency] = 0.0
        if quote_currency not in assets:
            assets[quote_currency] = 0.0
        
        # 取引を適用
        # amount > 0: 基軸通貨を買う（対象通貨を売る）
        # amount < 0: 基軸通貨を売る（対象通貨を買う）
        assets[base_currency] += amount
        assets[quote_currency] -= amount * rate
    
    # 現在のレートで全資産をJPY換算
    # total_jpy = 0.0
    # jpy_equivalent = {}
    
    # for currency, amount in assets.items():
    #     if currency == "JPY":
    #         jpy_value = amount
    #     elif currency == "USD":
    #         jpy_value = amount * current_rates.get("USDJPY", 148.0)
    #     elif currency == "EUR":
    #         jpy_value = amount * current_rates.get("EURJPY", 172.0)
    #     else:
    #         # 他の通貨の場合、デフォルトで1:1とする
    #         jpy_value = amount
        
    #     jpy_equivalent[currency] = jpy_value
    #     total_jpy += jpy_value
    
    # 結果を返す
    result = {
        "assets": assets,
        # "jpy_equivalent": jpy_equivalent,
        # "total_jpy": total_jpy,
        "transaction_count": transaction_log.get("total_count", len(transaction_log["transactions"]))
    }
    
    return result


def load_transaction_log_from_file(file_path: str) -> Dict:
    """
    ファイルからtransaction_logを読み込む
    
    Args:
        file_path (str): transaction_log.jsonのファイルパス
        
    Returns:
        Dict: transaction_logデータ
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def calculate_assets_from_file(log_file_path: str, initial_assets: Dict[str, float],) -> Dict[str, float]:
    """
    ファイルからtransaction_logを読み込んで資産計算を行う
    
    Args:
        log_file_path (str): transaction_log.jsonのファイルパス
        initial_assets (Dict[str, float]): 初期資産
        current_rates (Dict[str, float]): 現在のレート
        
    Returns:
        Dict[str, float]: 最終的な資産状況
    """
    transaction_log = load_transaction_log_from_file(log_file_path)
    return calculate_final_assets(transaction_log, initial_assets)


def print_asset_summary(log_file_path: str, current_rates: Dict[str, float]):
    """
    資産計算結果を見やすく表示する。ログ詳細・残高・総資産(JPY換算)も表示。

    Args:
        log_file_path (str): transaction_log.jsonのファイルパス
        current_rates (Dict[str, float]): 現在のレート {"USDJPY": 148.0, "EURJPY": 172.0}
    Returns:
        str: 表示用のまとめテキスト
    """

    transaction_log = load_transaction_log_from_file(log_file_path)
    result = calculate_final_assets(transaction_log, initial_assets)

    output = []
    output.append("=== 資産計算結果 ===")
    output.append(f"取引回数: {result['transaction_count']}")
    output.append("\n=== 各通貨残高 ===")
    for currency, amount in result["assets"].items():
        output.append(f"{currency}: {amount:,.2f}")

    # 総資産(JPY換算)の計算
    total_jpy = 0.0
    output.append("\n=== JPY換算残高 ===")
    for currency, amount in result["assets"].items():
        if currency == "JPY":
            jpy_value = amount
        elif currency == "USD":
            jpy_value = amount * current_rates.get("USDJPY", 148.0)
        elif currency == "EUR":
            jpy_value = amount * current_rates.get("EURJPY", 172.0)
        else:
            jpy_value = amount
        output.append(f"{currency}: {jpy_value:,.2f} JPY")
        total_jpy += jpy_value
    output.append(f"\n総資産(JPY換算): {total_jpy:,.2f} JPY")

    # 取引ログ詳細表示
    if "transactions" in transaction_log:
        output.append("\n=== 取引ログ詳細 ===")
        for _, tx in enumerate(transaction_log["transactions"], 1):
            ts = tx.get("timestamp", "")
            pair = tx.get("currency_pair", "")
            amt = tx.get("amount", 0.0)
            rate = tx.get("rate", 0.0)
            action = "買い" if amt > 0 else "売り"
            # 日付部分だけ抽出
            date_str = ts.split(" ")[0] if " " in ts else ts[:10]
            output.append(
                f"日付: {date_str}, 通貨ペア: {pair}, {action}, 数量: {abs(amt):,.2f}, レート: {rate:,.2f}"
            )
    else:
        output.append("\n取引ログ詳細は表示されません（transactions未指定）")

    summary = "\n".join(output)
    print(summary)
    return summary

# global
initial_assets = {
        "JPY": 100000.0,
        "USD": 0.0,
        "EUR": 0.0
    }

# 使用例
if __name__ == "__main__":
    
    # 初期資産（JPY: 10万円）
    
    
    # 現在のレート
    # current_rates = {
    #     "USDJPY": 148.0,
    #     "EURJPY": 172.0
    # }
    
    # ファイルパスを指定して計算
    log_file_path = "data/log/transaction_log.json"
    # tr_log = load_transaction_log_from_file(log_file_path)
        
    # 計算実行
    # result = calculate_final_assets(tr_log, initial_assets)
    
    result = calculate_assets_from_file(log_file_path, initial_assets)
    
    print(result)
    
    # 結果表示
    # print_asset_summary(result)
