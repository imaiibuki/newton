# Newton — ローカル AI コーディングアシスタント

完全ローカル動作のコーディングアシスタントです。Qwen3.5-9B を VRAM 12GB の GPU 上で動かし、VS Code の右クリックメニューやチャットパネルからコードの解析・修正・生成を行います。クラウド API への通信は一切行いません。

```
[VS Code 拡張 (TypeScript)]
        │ HTTP / SSE (localhost:8000)
        ▼
[推論サーバー (FastAPI)]
        │
        ▼
[Qwen3.5-9B — bitsandbytes NF4 4bit 量子化]
        │
        ▼
[NVIDIA GPU (VRAM 12GB)]
```

---

## 背景と目的

クラウド LLM が主流の現在でも、API 料金・使用制限・プライバシーといった課題は残ります。VRAM さえあれば完全オフラインで動かせるローカルコーディングアシスタントを目指して開発しました。

ローカル LLM の最大の壁は VRAM 容量にあります。TurboQuant による KV キャッシュ圧縮を組み合わせることでこの制約を緩和し、VRAM 12GB の GPU でも実用的な応答速度を実現しています。

## 設計方針

VRAM 効率を最優先とした二段構えの圧縮設計を採用しています。

- **モデル重み**: bitsandbytes NF4 4bit 量子化により、9B パラメータのモデルを約 7.65GB に収める
- **KV キャッシュ**: TurboQuant 3bit 圧縮により、長文コンテキストでの VRAM 圧迫を緩和する

Ollama はカスタム KV キャッシュ層への介入が困難なため、HuggingFace から直接モデルを取得し、transformers の `DynamicCache` を差し替える構成を採用しています。

モデルの選定は日本語・Python への適合性と VRAM 12GB での動作可否を軸に検討し、**Qwen3.5-9B** を採用しました。

## 制約と使い方のヒント

VRAM 効率の最大化を図っていますが、長大なコンテキストを維持し続ける用途には向いていません。クラウド LLM のような常時会話継続よりも、コードの特定箇所に対してスポット的に問い合わせる使い方で最も効果を発揮します。

## 動作要件

| 項目 | 要件 |
|------|------|
| OS | Windows 10/11 |
| GPU | NVIDIA (VRAM 12GB 推奨) |
| CUDA | 12.4 以上 |
| Python | 3.11 以上 |
| Node.js | 18 以上 (拡張のビルド時のみ) |
| VS Code | 1.90 以上 |

> VRAM が 8GB の場合は動作しますが、長いコンテキストで OOM が発生する可能性があります。

---

## セットアップ

### 1. リポジトリのクローン

```bash
git clone https://github.com/imaiibuki/newton.git
cd newton
```

### 2. Python 仮想環境の作成と依存パッケージのインストール

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 3. HuggingFace トークンの設定

Qwen3.5-9B のモデル重みのダウンロードに HuggingFace アカウントが必要です。

```powershell
$env:HF_TOKEN = "hf_xxxxxxxxxxxx"
```

### 4. 推論サーバーの起動

```powershell
python run_server.py
```

初回起動時はモデルのダウンロードが発生します（約 5GB）。  
以下のログが出たら準備完了です。

```
[Model] Ready. VRAM allocated: 7.65 GB / reserved: 7.81 GB
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 5. VS Code 拡張のインストール

**開発・デバッグ用（ソースから）:**

```powershell
cd newton-agent
npm install
npm run compile
```

VS Code で `newton-agent` フォルダを開いて `F5` を押すと Extension Development Host が起動します。

**ビルド済み .vsix からインストール:**

```
コマンドパレット → Extensions: Install from VSIX → newton-agent-x.x.x.vsix
```

---

## 機能

### Explain — コード解説

コードを選択して右クリック → **Newton: Explain**  
選択範囲の説明・問題点・改善案をチャットパネルにストリーミング表示します。

### Fix Error — エラー修正

コードを選択して右クリック → **Newton: Fix Error**  
VS Code の診断（赤波線）があれば自動取得、なければ入力ボックスでエラーメッセージを貼り付けます。  
結果パネルの **Show Diff** ボタンで修正前後を diff エディタで確認できます。

### Generate — コード生成

コマンドパレット → **Newton: Generate Code**  
日本語で仕様を入力するとコードを生成します。

### Generate Tests — テスト生成

コードを選択して右クリック → **Newton: Generate Tests**  
pytest ユニットテストを生成します。

### Add Docstring — ドキュメント生成

コードを選択して右クリック → **Newton: Add Docstring**  
Google-style docstring を追加したコードを生成します。

### Generate Commit Message — コミットメッセージ生成

SCM サイドバーのタイトルバー → **Newton: Generate Commit Message**  
`git diff --staged` の内容から日本語コミットメッセージを自動生成して入力欄に反映します。

### Chat — チャットパネル

コマンドパレット → **Newton: Open Chat**  
コード・ファイル・フォルダを添付して自由に質問できます。

---

## ステータスバー

VS Code 右下に常時表示されます。

| 表示 | 状態 |
|------|------|
| `⟳ Newton` | 起動確認中 |
| `● Newton 7.65/12.88GB` | 稼働中・VRAM使用量 |
| `○ Newton (loading)` | モデルロード中 |
| `⊘ Newton (offline)` | サーバーに接続できない |

---

## ディレクトリ構成

```
newton/
├── run_server.py          サーバー起動スクリプト
├── start_server.bat       Windows バッチ起動スクリプト
├── test_server.py         動作確認スクリプト
├── requirements.txt       Python 依存パッケージ
├── server/
│   ├── main.py            FastAPI エントリーポイント・全エンドポイント
│   ├── model.py           Qwen3.5-9B ロード・ストリーミング推論
│   ├── prompts.py         各エンドポイント用プロンプトビルダー
│   ├── context.py         ファイルコンテキスト・import 依存解析・フォルダ収集
│   └── tools/
│       └── file_ops.py    ファイル読み取りユーティリティ
└── newton-agent/          VS Code 拡張
    ├── package.json
    ├── tsconfig.json
    └── src/
        ├── extension.ts   コマンド登録・ステータスバー・ヘルスポーリング
        ├── panel.ts        ChatPanel（Webview UI・SSE受信・コンテキスト添付）
        ├── editorContext.ts 選択テキスト・言語・診断エラー・workspaceRoot 取得
        └── diffProvider.ts newton-diff:// スキームの TextDocumentContentProvider
```

---

## API エンドポイント

サーバー起動後、Swagger UI で確認できます: `http://localhost:8000/docs`

| エンドポイント | 説明 |
|---|---|
| `POST /chat` | チャット（mode で analyze / fix / generate / test / document を切り替え） |
| `POST /analyze` | コード解析・説明（SSE ストリーミング） |
| `POST /fix` | エラー修正案の生成（SSE ストリーミング） |
| `POST /generate` | 日本語仕様 → コード生成（SSE ストリーミング） |
| `POST /commit` | git diff → 日本語コミットメッセージ生成 |
| `POST /cancel` | 進行中の生成を中断 |
| `GET /health` | サーバー稼働状態・VRAM使用量 |

---

## 技術的な詳細

| 項目 | 内容 |
|------|------|
| モデル | Qwen/Qwen3.5-9B |
| 量子化 | bitsandbytes NF4 4bit |
| VRAM 使用量 | 約 7.65 GB |
| KV キャッシュ | TurboQuant 3bit (full_attention) + LinearAttentionLayer (linear_attention) |
| アテンション | Flash Attention 2（利用可能な場合）/ SDPA |
| ストリーミング | TextIteratorStreamer + SSE |
| プレフィックスキャッシュ | システムプロンプト部分の KV を再利用して2回目以降の応答を高速化 |

**`device_map={"": 0}` を使う理由:**  
`device_map="auto"` は非量子化レイヤーを CPU に送ることがあり、bitsandbytes との互換性エラーが発生します。全レイヤーを `cuda:0` に固定することで回避しています。

---

## 制限事項

- Windows 専用（起動スクリプトが PowerShell / バッチ前提）
- LLM は直接ファイルを書き換えません。Fix 系の結果はユーザーが確認して適用します
- 大きなファイルはサーバー側で文字数制限により切り詰められます（単体 6,000 文字、依存収集合計 32,000 文字）
- 使用前に `run_server.py` を別ターミナルで起動しておく必要があります

---

## トラブルシューティング

**`ModuleNotFoundError: No module named 'uvicorn'`**  
→ VS Code がシステムの Python を参照しています。`Ctrl+Shift+P` → **Python: Select Interpreter** → `venv\Scripts\python.exe` を選択してください。

**ステータスバーが `⊘ Newton (offline)`**  
→ `run_server.py` が起動していません。別ターミナルで起動してください。

**Fix Error でエラーが自動取得されない**  
→ 言語サーバー（Pylance 等）がまだ診断を報告していない場合があります。入力ボックスにエラーメッセージを手動で貼り付けてください。

---

## ライセンス

[MIT License](LICENSE)
