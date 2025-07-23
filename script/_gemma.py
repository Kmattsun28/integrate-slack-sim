import os
import argparse
import torch
from transformers import AutoProcessor, Gemma3ForConditionalGeneration

# モデルを事前にロードする関数
def load_model(model_id="google/gemma-3-27b-it", cache_dir="/mnt/bigdata/88_HuggingFaceCache"):
# def load_model(model_id="google/gemma-3-27b-it", cache_dir="/home/aoi_ucl/.cache/huggingface"):
    """
    Gemmaモデルとプロセッサをロードする
    
    Args:
        model_id: 使用するモデルのID
        cache_dir: モデルとプロセッサーのキャッシュディレクトリ
    
    Returns:
        (model, processor): ロードされたモデルとプロセッサのタプル
    """
    # 高精度の行列乗算を設定
    torch.set_float32_matmul_precision("high")
    
    # キャッシュサイズ制限の増加
    torch._dynamo.config.cache_size_limit = 512
    
    # キャッシュディレクトリが存在しなければ作成
    if cache_dir and not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)
        print(f"キャッシュディレクトリを作成しました: {cache_dir}")
    
    try:
        # モデルとプロセッサーのロード
        print(f"モデル {model_id} をロード中...")
        model = Gemma3ForConditionalGeneration.from_pretrained(
            model_id,
            device_map="auto",
            cache_dir=cache_dir
        ).eval()
        processor = AutoProcessor.from_pretrained(model_id, cache_dir=cache_dir)
        print("モデルのロード完了")
        return model, processor
    
    except Exception as e:
        print(f"モデルのロード中にエラーが発生しました: {str(e)}")
        return None, None

# 既存のモデルを使って推論を実行する関数
def run_inference_with_loaded_model(model, processor, prompt, output_path=None):
    """
    既にロードされたモデルを使用して推論を実行する
    
    Args:
        model: ロード済みのGemmaモデル
        processor: ロード済みのプロセッサ
        prompt: 入力プロンプト文字列
        output_path: 出力ファイルのパス（省略可能）
    
    Returns:
        (response, output_path): 生成されたテキストと保存先のパス
    """
    try:
        # 推論の実行
        print("推論を実行中...")
        
        # Gemmaのチャットテンプレートを使用
        messages = [
            {
                "role": "system",
                "content": [{"type": "text", "text": "You are a helpful assistant."}]
            },
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}]
            }
        ]
        
        inputs = processor.apply_chat_template(
            messages, 
            add_generation_prompt=True, 
            tokenize=True,
            return_dict=True, 
            return_tensors="pt"
        ).to(model.device, dtype=torch.bfloat16)
        
        input_len = inputs["input_ids"].shape[-1]
        
        with torch.inference_mode():
            generation = model.generate(
                **inputs, 
                max_new_tokens=50000,
                do_sample=False
            )
            generation = generation[0][input_len:]
        
        response = processor.decode(generation, skip_special_tokens=True)
        
        # 結果の保存（output_pathが指定されている場合）
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(response)
            print(f"結果を保存しました: {output_path}")
        
        return response, output_path
    
    except Exception as e:
        print(f"推論中にエラーが発生しました: {str(e)}")
        return None, None

# 既存の関数（後方互換性のため残す）
def run_inference_on_single_prompt(prompt_path, model_id="google/gemma-3-27b-it", output_path=None, cache_dir="/mnt/bigdata/88_HuggingFaceCache", 
                                   model=None, processor=None):
    """
    指定されたプロンプトファイルに対してGemmaモデルで推論を実行し、結果を保存
    
    Args:
        prompt_path: プロンプトファイルのパス
        model_id: 使用するモデルのID（model引数が指定されていない場合に使用）
        output_path: 出力ファイルのパス（指定しない場合はプロンプトファイルと同じディレクトリに保存）
        cache_dir: モデルとプロセッサーのキャッシュディレクトリ
        model: 事前にロードされたモデル（指定されている場合はこちらを使用）
        processor: 事前にロードされたプロセッサ（指定されている場合はこちらを使用）
    
    Returns:
        生成されたレスポンス
    """
    # プロンプトファイルの存在確認
    if not os.path.exists(prompt_path):
        raise FileNotFoundError(f"プロンプトファイルが見つかりません: {prompt_path}")
    
    # プロンプトの読み込み
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt = f.read()
    
    print(f"プロンプトを読み込みました: {prompt_path}")
    
    try:
        # モデルとプロセッサーが指定されていない場合はロードする
        should_unload = False
        if model is None or processor is None:
            model, processor = load_model(model_id, cache_dir)
            should_unload = True  # この関数内でロードした場合は解放する
        
        if model is None or processor is None:
            raise ValueError("モデルまたはプロセッサのロードに失敗しました")
        
        # デフォルトの出力パスを設定（指定がない場合）
        if output_path is None:
            # デフォルトでは同じディレクトリにresponse_gemma27.txtとして保存
            result_dir = os.path.dirname(prompt_path)
            output_path = os.path.join(result_dir, "response_gemma27.txt")
        
        # 推論の実行
        response, saved_path = run_inference_with_loaded_model(model, processor, prompt, output_path)
        
        # この関数内でモデルをロードした場合は明示的に解放
        if should_unload:
            del model
            del processor
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        
        return response, saved_path
    
    except Exception as e:
        print(f"エラーが発生しました: {str(e)}")
        # エラーログの保存
        error_path = os.path.join(os.path.dirname(prompt_path), "error_gemma27.log")
        with open(error_path, "w", encoding="utf-8") as f:
            f.write(f"エラー: {str(e)}")
        return None

def main():
    # コマンドライン引数の解析
    parser = argparse.ArgumentParser(description='単一のプロンプトファイルに対してGemmaモデルで推論を実行します')
    parser.add_argument('prompt_path', help='プロンプトファイルのパス')
    parser.add_argument('--model', '-m', default="google/gemma-3-27b-it", help='使用するモデルのID')
    parser.add_argument('--output', '-o', help='出力ファイルのパス（指定しない場合は入力ファイルと同じディレクトリに保存）')
    parser.add_argument('--cache-dir', default='/mnt/bigdata/88_HuggingFaceCache', help='モデルとプロセッサーのキャッシュディレクトリ')
    
    args = parser.parse_args()
    
    # 推論の実行
    run_inference_on_single_prompt(
        prompt_path=args.prompt_path,
        model_id=args.model,
        output_path=args.output,
        cache_dir=args.cache_dir
    )

if __name__ == "__main__":
    main()