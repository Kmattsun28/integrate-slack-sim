# LLM Real Transaction & Forex Slack Bot 統合プロジェクト

## 概要
このプロジェクトは、為替取引の推論・シミュレーションとSlack連携を統合したシステムです。
- `inference.py`：LLMによる為替推論・シミュレーション
- `forex_slack_bot/`：Slackボットによる通知・コマンド受付
- `data/`：残高・取引ログ・推論結果の保存

## ディレクトリ構成
```
llm_real_transaction/
├── inference.py
├── data/
│   ├── balance/balance.json
│   ├── log/transaction_log.json
│   └── real_out/
├── forex_slack_bot/
│   ├── app.py
│   ├── config.py
│   ├── handlers/
│   ├── models/
│   ├── schedulers/
│   ├── services/
│   └── utils/
├── script/
│   ├── create_prompt.py
│   ├── fetch.py
│   ├── handle_transaction_log.py
│   ├── llm_strategy.py
│   ├── portfolio.py
│   └── _gemma.py
└── README.md
```

## セットアップ手順
1. 必要なPythonパッケージをインストール
   ```zsh
   pip install -r requirements.txt
   ```
2. CUDA対応torchのインストール（GPU利用の場合）
   ```zsh
   uv pip install torch==2.5.1+cu121 --extra-index-url https://download.pytorch.org/whl/cu121
   ```
   - `uv`は高速なPythonパッケージマネージャです。未インストールの場合は`pip install uv`で導入してください。
3. `.env`ファイルを`forex_slack_bot/`に作成し、Slack APIキー等を設定
   - 例：
     ```
     SLACK_BOT_TOKEN=your-slack-bot-token
     SLACK_SIGNING_SECRET=your-signing-secret
     SLACK_APP_TOKEN=your-app-token
     DEFAULT_CHANNEL=#forex-trading
     ADMIN_CHANNEL=#admin
     INITIAL_BALANCE_JPY=1000000.0
     LOG_LEVEL=INFO
     ```
4. データディレクトリの作成（初回起動時に自動作成されます）
   - `data/balance/balance.json`：残高ファイル
   - `data/log/transaction_log.json`：取引ログ
   - `data/real_out/`：推論結果保存先

## 実行方法

### 1. Slackボットの起動
Slack連携やコマンド受付を行う場合は、以下のコマンドでSlackボットを起動します。
```zsh
cd forex_slack_bot
python app.py
```
- Slackワークスペースで `/inference` コマンドを送信すると、推論が実行されます。

### 2. 推論の手動実行
コマンドラインから直接推論を実行したい場合は、以下のコマンドを使用します。
```zsh
python inference.py --transaction_file data/log/transaction_log.json --output_dir data/real_out
```
- 推論結果とプロンプトは `data/real_out/{timestamp}` に保存されます。

### 3. 実行前の前提
- `.env` ファイルが `forex_slack_bot/` に存在し、Slack APIキー等が正しく設定されていること。
- `data/` ディレクトリが存在し、必要なファイル（balance.json, transaction_log.json）が初回起動時に自動生成されていること。

## 主な依存パッケージ
- slack_bolt
- python-dotenv
- pandas
- yfinance
- torch
- transformers
- apscheduler
- uv

## 注意事項
- GPUメモリ解放のため、推論は毎回サブプロセスで実行されます。
- Slackコマンド`/inference`で推論を実行可能です。
# integrate-slack-sim
