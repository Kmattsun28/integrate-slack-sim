import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import yfinance as yf
import os
import json
import hashlib
import pickle

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import yfinance as yf
import os
import json
import hashlib
import pickle
import requests

# キャッシュ設定
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', 'cache')
CACHE_EXPIRY_MINUTES = 2  # キャッシュの有効期限（分）

def get_cache_key(symbol, start_time, end_time, interval):
    """キャッシュキーを生成する"""
    key_string = f"{symbol}_{start_time}_{end_time}_{interval}"
    return hashlib.md5(key_string.encode()).hexdigest()

def get_cache_filepath(cache_key):
    """キャッシュファイルのパスを取得する"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"yfinance_{cache_key}.pkl")

def is_cache_valid(filepath, expiry_minutes=CACHE_EXPIRY_MINUTES):
    """キャッシュが有効かどうかをチェックする"""
    if not os.path.exists(filepath):
        return False
    
    # ファイルの最終更新時刻を取得
    file_mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
    expiry_time = datetime.now() - timedelta(minutes=expiry_minutes)
    
    return file_mtime > expiry_time

def save_to_cache(data, cache_key):
    """データをキャッシュに保存する"""
    try:
        filepath = get_cache_filepath(cache_key)
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
        print(f"キャッシュに保存しました: {cache_key}")
    except Exception as e:
        print(f"キャッシュ保存エラー: {e}")

def load_from_cache(cache_key):
    """キャッシュからデータを読み込む"""
    try:
        filepath = get_cache_filepath(cache_key)
        if is_cache_valid(filepath):
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            print(f"キャッシュから読み込みました: {cache_key}")
            return data
    except Exception as e:
        print(f"キャッシュ読み込みエラー: {e}")
    return None

def download_with_cache(symbol, interval, start, end, use_cache=True):
    """キャッシュ機能付きのyfinance.download"""
    # キャッシュキーを生成
    cache_key = get_cache_key(symbol, start.isoformat(), end.isoformat(), interval)
    
    # キャッシュが有効な場合は使用
    if use_cache:
        cached_data = load_from_cache(cache_key)
        if cached_data is not None:
            return cached_data
    
    # キャッシュが無い場合は新しくダウンロード
    print(f"yfinanceからダウンロード中: {symbol} {interval} {start} - {end}")
    df = yf.download(symbol, interval=interval, start=start, end=end, 
                     group_by=False, prepost=True, progress=False)
    
    # キャッシュに保存
    if use_cache:
        save_to_cache(df, cache_key)
    
    return df

def clear_cache(older_than_hours=24):
    """古いキャッシュファイルを削除する"""
    if not os.path.exists(CACHE_DIR):
        return
    
    cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
    deleted_count = 0
    
    for filename in os.listdir(CACHE_DIR):
        if filename.startswith('yfinance_') and filename.endswith('.pkl'):
            filepath = os.path.join(CACHE_DIR, filename)
            file_mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
            
            if file_mtime < cutoff_time:
                try:
                    os.remove(filepath)
                    deleted_count += 1
                except Exception as e:
                    print(f"キャッシュファイル削除エラー: {e}")
    
    if deleted_count > 0:
        print(f"{deleted_count}個の古いキャッシュファイルを削除しました")

def fetch_forex_technicals(symbol, base_time_jst, save_to_file=False, use_cache=True):
    """
    指定された通貨ペアと日時のテクニカル指標データを取得する
    
    Args:
        symbol (str): 通貨ペア (例: "USDJPY=X")
        base_time_jst (datetime): 基準日時（日本時間）
        save_to_file (bool): 結果をファイルに保存するかどうか
        use_cache (bool): キャッシュを使用するかどうか
    
    Returns:
        dict: テクニカル指標データを含む辞書
            - hourly_data: 1時間足データ（RSI付き）
            - daily_data: 日足データ（SMA付き）
            - indicators: MACD等の指標値
    """
    
    # 文字列ならdatetimeに変換
    if isinstance(base_time_jst, str):
        base_time_jst = datetime.strptime(base_time_jst, "%Y-%m-%d %H:%M:%S")
    
    # 各種テクニカル指標計算関数
    def calc_rsi(series, period=14):
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        
        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calc_sma(series, period=20):
        return series.rolling(window=period, min_periods=period).mean()
    
    def calc_macd(series, fast=12, slow=26, signal=9):
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        return macd_line, signal_line
    
    def flatten_yfinance_columns(df):
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[1] if col[1] else col[0] for col in df.columns]
        else:
            df.columns = [col.split("_")[-1] for col in df.columns]
        return df
    
    # JST -> UTC変換
    base_time_utc = base_time_jst - timedelta(hours=9)
    
    # 1. 1時間足データ取得とRSI計算
    start_1h = base_time_utc - timedelta(hours=72)
    end_1h = base_time_utc
    
    df_1h = download_with_cache(symbol, "1h", start_1h, end_1h, use_cache)
    df_1h = flatten_yfinance_columns(df_1h)
    
    hourly_data = None
    if len(df_1h) > 0:
        df_1h['RSI_14'] = calc_rsi(df_1h['Close'], period=14)
        df_1h = df_1h.dropna()
        
        # 最新6時間分を抽出
        latest_6 = df_1h.iloc[-min(6, len(df_1h)):][['Open', 'Close', 'RSI_14']]
        latest_6.index = latest_6.index.tz_localize(None)  # タイムゾーン除去
        
        # 時間足データを整形
        hourly_data = []
        for timestamp, row in latest_6.iloc[::-1].iterrows():
            if isinstance(timestamp, pd.Timestamp):
                time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            else:
                time_str = f"Hour-{len(hourly_data)}"
                
            hourly_data.append({
                "time": time_str,
                "open": float(row["Open"]),
                "close": float(row["Close"]),
                "rsi_14": float(row["RSI_14"] if "RSI_14" in row else row[2])
            })
    
    # 2. 4時間足データ取得とSMA、MACD計算
    start_4h = base_time_utc - timedelta(days=10)
    end_4h = base_time_utc
    
    df_4h = download_with_cache(symbol, "4h", start_4h, end_4h, use_cache)
    df_4h = flatten_yfinance_columns(df_4h)
    
    daily_data = None
    macd_value = 0.0012  # デフォルト値
    signal_value = 0.0008  # デフォルト値
    
    if len(df_4h) > 0:
        # SMA計算
        df_4h['SMA_20'] = calc_sma(df_4h['Close'], period=min(20, len(df_4h)))
        
        # MACD計算
        macd_line, signal_line = calc_macd(df_4h['Close'])
        df_4h['MACD'] = macd_line
        df_4h['Signal'] = signal_line
        
        df_4h = df_4h.dropna()
        
        if len(df_4h) > 0:
            # タイムゾーン調整
            df_4h.index = df_4h.index + timedelta(hours=9)  # UTC → JST
            df_4h["date"] = df_4h.index.date
            
            # 日ごとの始値・終値を集約
            daily_agg = df_4h.groupby("date").agg({
                "Open": "first",  
                "Close": "last", 
                "SMA_20": "last"
            })
            latest_3d = daily_agg.iloc[-min(3, len(daily_agg)):]
            
            # 最新のMACDとシグナルを取得
            macd_value = df_4h['MACD'].iloc[-1]
            signal_value = df_4h['Signal'].iloc[-1]
            
            # 日足データを整形
            daily_data = []
            for date, row in latest_3d.iterrows():
                if isinstance(date, pd.Timestamp):
                    date_str = date.strftime("%Y-%m-%d")
                else:
                    date_str = str(date)
                    
                daily_data.append({
                    "date": date_str,
                    "open": float(row["Open"]),
                    "close": float(row["Close"]),
                    "sma_20": float(row["SMA_20"])
                })
    
    # 結果をまとめる
    result = {
        "meta": {
            "symbol": symbol,
            "base_time_jst": base_time_jst.strftime("%Y-%m-%d %H:%M"),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        },
        "hourly": hourly_data or [],
        "daily": daily_data or [],
        "indicators": {
            "macd": float(macd_value),
            "macd_signal": float(signal_value)
        }
    }
    
    # ファイル保存オプション
    if save_to_file:
        filename = f"forex_technicals_{symbol.replace('=', '')}_{base_time_jst.strftime('%Y%m%d_%H%M')}.json"
        with open(filename, 'w') as f:
            import json
            json.dump(result, f, indent=4, ensure_ascii=False)
    
    return result

    return technical_data

def fetch_news_at_time(base_time, hours_back=24, limit=10, currencies=None, api_url="http://192.168.207.239:18000/api/news/at"):
    """
    指定された日時より前の一定時間内のニュース記事を取得する関数
    
    Args:
        base_time (datetime): 基準日時
        hours_back (int): 何時間前までのニュースを取得するか
        limit (int): 取得する記事の最大数
        currencies (list): フィルタリング対象の通貨リスト (例: ["USD", "JPY", "EUR"])
        api_url (str): APIのエンドポイント
        
    Returns:
        list: ニュース記事のリスト、エラーの場合は空リスト
    """
    news_articles = []
    
    try:
        
        # 文字列ならdatetimeに変換
        if isinstance(base_time, str):
            base_time = datetime.strptime(base_time, "%Y-%m-%d %H:%M:%S")
        
        # 日時をISO形式に変換
        date_time_iso = base_time.isoformat()
        
        # APIリクエストのパラメータを構築
        params = {
            "date_time": date_time_iso,
            "hours_back": hours_back,
            "limit": limit
        }
        
        # 通貨フィルターが指定されている場合は追加
        if currencies:
            if isinstance(currencies, str):
                # 文字列の場合はリストに変換
                currencies = [currencies]
            # 複数の通貨パラメータを正しく送信するため、paramsを修正
            params["currencies"] = currencies
        
        # APIリクエストを送信
        # 通貨パラメータを正しく送信するために、手動でクエリ文字列を構築
        if currencies:
            # 基本パラメータを構築
            query_params = []
            query_params.append(f"date_time={date_time_iso}")
            query_params.append(f"hours_back={hours_back}")
            query_params.append(f"limit={limit}")
            
            # 通貨パラメータを追加（各通貨ごとに currencies= を繰り返す）
            for currency in currencies:
                query_params.append(f"currencies={currency}")
            
            # 完全なURLを構築
            full_url = f"{api_url}?{'&'.join(query_params)}"
            print(f"リクエストURL: {full_url}")  # デバッグ用ログ
            response = requests.get(full_url)
        else:
            # 通貨フィルターが無い場合は通常のパラメータ使用
            response = requests.get(api_url, params=params)
        
        # レスポンスを処理
        if response.status_code == 200:
            api_data = response.json()
            news_articles = [
                {
                    "title": article["title"],
                    "summary": article["summary"],
                    "url": article["url"],
                    "published": article["published"]
                }
                for article in api_data.get("articles", [])
            ]
            print(f"{len(news_articles)}件のニュース記事を取得しました")
        else:
            print(f"APIエラー: {response.status_code} - {response.text}")
    
    except Exception as e:
        print(f"ニュース取得中にエラーが発生しました: {str(e)}")
    
    return news_articles

# fetch_forex_technicalsの結果に直接ニュースを追加する関数
def fetch_forex_technicals_with_news(symbol, base_time_jst, news_base_time, hours_back=24, limit=10, currencies=None, api_url="http://192.168.207.239:18000/api/news/at", save_to_file=False, output_dir=None, use_cache=True):
    """
    テクニカル指標データとニュース情報を一括取得する
    
    Args:
        symbol (str): 通貨ペア (例: "USDJPY=X")
        base_time_jst (datetime): 基準日時（日本時間）- テクニカル指標用
        news_base_time (datetime): ニュース取得用の基準日時（UTC）
        hours_back (int): 何時間前までのニュースを取得するか
        limit (int): 取得する記事の最大数
        currencies (list): フィルタリング対象の通貨リスト (例: ["USD", "JPY", "EUR"])
        api_url (str): ニュースAPIのエンドポイント
        save_to_file (bool): 結果をファイルに保存するかどうか
        output_dir (str): 出力ディレクトリ
        use_cache (bool): キャッシュを使用するかどうか
        
    Returns:
        dict: テクニカル指標データとニュース情報を含む辞書
    """
    # まずテクニカル指標を取得（既存の関数を使用）
    technical_data = fetch_forex_technicals(symbol, base_time_jst, save_to_file=False, use_cache=use_cache)
    
    # ニュース記事を取得
    news_time = news_base_time
    news_articles = fetch_news_at_time(news_time, hours_back, limit, currencies, api_url)
    
    # データにニュースを追加
    technical_data["news"] = news_articles
    
    # ファイル保存オプション
    if save_to_file:
        save_dir = output_dir or "."
        os.makedirs(save_dir, exist_ok=True)
        filename = f"forex_technicals_{symbol.replace('=', '')}_{base_time_jst.strftime('%Y%m%d_%H%M')}.json"
        filepath = os.path.join(save_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(technical_data, f, indent=2, ensure_ascii=False)
            print(f"データを保存しました: {filepath}")
        except Exception as e:
            print(f"ファイル保存中にエラーが発生しました: {e}")
    
    return technical_data


def get_cache_info():
    """キャッシュの情報を取得する"""
    if not os.path.exists(CACHE_DIR):
        return {"cache_dir": CACHE_DIR, "cache_files": 0, "total_size": 0}
    
    cache_files = []
    total_size = 0
    
    for filename in os.listdir(CACHE_DIR):
        if filename.startswith('yfinance_') and filename.endswith('.pkl'):
            filepath = os.path.join(CACHE_DIR, filename)
            file_size = os.path.getsize(filepath)
            file_mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
            
            cache_files.append({
                "filename": filename,
                "size": file_size,
                "modified": file_mtime.strftime("%Y-%m-%d %H:%M:%S"),
                "is_valid": is_cache_valid(filepath)
            })
            total_size += file_size
    
    return {
        "cache_dir": CACHE_DIR,
        "cache_files": len(cache_files),
        "total_size": total_size,
        "files": cache_files
    }

def benchmark_cache_performance(symbol="USDJPY=X", base_time_jst=None):
    """キャッシュの性能をベンチマークする"""
    if base_time_jst is None:
        base_time_jst = datetime.now()
    
    import time
    
    print("=== キャッシュ性能ベンチマーク ===")
    
    # キャッシュなしでの実行時間を測定
    start_time = time.time()
    result_no_cache = fetch_forex_technicals(symbol, base_time_jst, use_cache=False)
    time_no_cache = time.time() - start_time
    print(f"キャッシュなし: {time_no_cache:.2f}秒")
    
    # キャッシュありでの実行時間を測定（初回）
    start_time = time.time()
    result_with_cache_first = fetch_forex_technicals(symbol, base_time_jst, use_cache=True)
    time_with_cache_first = time.time() - start_time
    print(f"キャッシュあり（初回）: {time_with_cache_first:.2f}秒")
    
    # キャッシュありでの実行時間を測定（2回目 - キャッシュヒット）
    start_time = time.time()
    result_with_cache_second = fetch_forex_technicals(symbol, base_time_jst, use_cache=True)
    time_with_cache_second = time.time() - start_time
    print(f"キャッシュあり（2回目）: {time_with_cache_second:.2f}秒")
    
    # 性能向上の計算
    speedup = 0
    if time_with_cache_second > 0:
        speedup = time_no_cache / time_with_cache_second
        print(f"速度向上: {speedup:.1f}倍")
    
    return {
        "no_cache": time_no_cache,
        "with_cache_first": time_with_cache_first,
        "with_cache_second": time_with_cache_second,
        "speedup": speedup
    }

# 使用例とテスト
if __name__ == "__main__":
    # キャッシュ情報を表示
    cache_info = get_cache_info()
    print(f"キャッシュディレクトリ: {cache_info['cache_dir']}")
    print(f"キャッシュファイル数: {cache_info['cache_files']}")
    print(f"総サイズ: {cache_info['total_size']} bytes")
    
    # 古いキャッシュをクリア
    clear_cache(older_than_hours=24)
    
    # ベンチマークを実行
    # benchmark_cache_performance()
    
    print("キャッシュ機能が有効になりました！")

