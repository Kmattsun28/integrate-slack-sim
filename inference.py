import sys
import os
import gc
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import datetime as dt
import torch
from script import llm_strategy
from script.portfolio import Portfolio
from script.create_prompt import create_prompt
from script._gemma import load_model, run_inference_with_loaded_model
from script.handle_transaction_log import calculate_assets_from_file
import argparse

portfolio = None

def printgreen(text):
    """緑色でテキストを表示"""
    print(f"\033[92m{text}\033[0m")

def run_inference(start: dt.datetime, current_assets: dict, transaction_file: str = None, output_dir: str = None):
    """transaction_fileを使用して推論を実行、判断を出力"""
    global portfolio

    jst_time = start + dt.timedelta(hours=9)
    printgreen(f" <<<< Starting inference {jst_time} (JST) : {current_assets} >>>>")
    portfolio = Portfolio(balances=current_assets)
    current_time_utc = start  # UTCで指定された開始時刻
    symbols = ["USDJPY", "EUR/JPY", "EUR/USD"]  # シミュレーションする通貨ペア
    
    #  modelとプロセッサーのロード
    printgreen("[STEP1] Loading model and processor")
    model, processor = None, None
    try:
        model, processor = load_model(model_id="google/gemma-3-12b-it")
    except Exception as e:
        print(f"モデルのロードに失敗しました: {e}")
        return portfolio
    
    # 出力ディレクトリの設定
    # now_jst_str = (dt.datetime.now() + dt.timedelta(hours=9)).strftime("%Y%m%d_%H%M%S")
    if output_dir is None:
        base_dir = os.path.join(os.getcwd(), "data/real_out")
        now_str = current_time_utc.strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(base_dir, now_str)
    os.makedirs(output_dir, exist_ok=True) 
    
    # シミュレーション履歴の記録用
    # simulation_log = os.path.join(output_dir, "simulation_log.txt")
    # with open(simulation_log, "w", encoding="utf-8") as f:
    #     f.write(f"シミュレーション開始: {start} (UTC)\n")
    #     f.write(f"初期資産: {portfolio}\n\n")


    # プロンプト生成
    printgreen("[STEP2]create_prompt")
    # 通貨ペアごとに自動的に適切な通貨フィルターを適用
    prompt, pair_current_rates = create_prompt(current_time_utc, symbols, portfolio, currencies=None, transaction_file=transaction_file)
    if pair_current_rates is None:
        printgreen("レート取得に失敗したため、推論をスキップします。")
        exit(1)
        # with open(simulation_log, "a", encoding="utf-8") as f:
        #     f.write(f"{current_time_utc} (UTC): レート取得失敗\n")
        # current_time_utc += dt.timedelta(hours=1)
        # continue

    # プロンプト保存
    prompt_path = os.path.join(output_dir, "prompt.txt")
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(prompt)

    # 推論実行
    printgreen("[STEP3] Inference with loaded model")
    response_data = run_inference_with_loaded_model(
        model, 
        processor, 
        prompt, 
        os.path.join(output_dir, "response.txt")
    )

    # 戻り値のチェック
    if response_data is None or response_data[0] is None:
        printgreen("推論に失敗しました。終了します。")
        exit(1)
        # ログに記録

    # タプルから値を取り出す
    response, saved_path = response_data
    
    if response is not None:
        print(f"生成されたレスポンス: {response[:100]}...")  # 先頭部分を表示
        print(f"保存先: {saved_path}")
    else:
        print("処理中にエラーが発生しました")
        
    # レスポンスから意思決定を抽出
    decisions = llm_strategy.extract_decisions(response)

    if decisions is None:
        printgreen("取引指示が抽出できませんでした。")
        exit(1)

    print("================================")
    print(f"抽出された取引指示: {decisions}")
    print("================================")
    
    # メモリ管理
    # gc.collect()
    # if torch.cuda.is_available():
    #     torch.cuda.empty_cache()
    
    # # モデルのメモリ解放
    # del model
    # del processor
    # gc.collect()
    # if torch.cuda.is_available():
    #     torch.cuda.empty_cache()

    return decisions


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Run forex simulation.")
    parser.add_argument("--transaction_file", type=str, default="data/log/transaction_log.json", help="Path to the transaction file")
    parser.add_argument("--output_dir", type=str, default=None, help="Output directory for logs and results")
    args = parser.parse_args()

    start_utc = dt.datetime.utcnow()
    
    # 初期資産（JPY: 10万円）
    initial_assets = {
        "JPY": 100000.0,
        "USD": 0.0,
        "EUR": 0.0
    }

    result = calculate_assets_from_file(args.transaction_file, initial_assets)
    assets = result.get("assets", {})

    out = run_inference(
        start=start_utc,
        current_assets=assets,
        transaction_file=args.transaction_file,
        output_dir=args.output_dir
    )
    printgreen("推論結果:")
    for decision in out:
        printgreen(f"  - 行動: {decision.get('action')}, 通貨ペア: {decision.get('symbol')}, 量: {decision.get('quantity')}")
    # GPUメモリ解放後、プロセス終了
    import gc
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass
    import sys
    sys.exit(0)