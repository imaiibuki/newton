# Newton — ローカルLLMコーディングアシスタント ガイド

---

## Newton とは

Newton は、インターネットに一切接続せずに動作する、**完全ローカル完結型のコーディングアシスタント**です。

RTX 4070 SUPER (VRAM 12GB) 上でオープンソースLLM（Qwen3.5-9B）を動かし、VS Code の右クリックメニューやコマンドパレットからコードの解析・修正・生成を行います。クラウド API への通信は一切行いません。

### 設計思想

ローカル9Bモデルの現実的な能力を踏まえ、「プロジェクト全体を自律的に管理するエージェント」ではなく、**スコープ固定の即答ツール**として設計しています。

- LLM はテキスト生成に専念する（ファイルを自分で読みに行くようなことはしない）
- 操作の対象は「選択範囲」または「現在のファイル」に限定する
- ファイル書き込みなどの破壊的操作は LLM が直接行わず、ユーザーが確認してから適用する

---

## システム全体像

```
┌──────────────────────────────────────────────────┐
│              VS Code (newton-agent 拡張)          │
│                                                  │
│  右クリック → Explain          チャットパネル     │
│  右クリック → Fix Error   →   ストリーミング表示  │
│  コマンド   → Open Chat        diff エディタ      │
│  ステータスバー: ● Newton 7.65/12.88GB           │
└──────────────────────┬───────────────────────────┘
                       │ HTTP (localhost:8000)
                       │ Server-Sent Events (SSE)
┌──────────────────────▼───────────────────────────┐
│            推論サーバー (FastAPI)                 │
│                                                  │
│  /analyze  コード解析・説明                       │
│  /fix      エラー修正案の生成                     │
│  /generate 日本語仕様 → コード生成               │
│  /chat     マルチモードチャット                   │
│  /commit   git diff → コミットメッセージ          │
│  /health   稼働状態・VRAM使用量                  │
└──────────────────────┬───────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────┐
│         Qwen3.5-9B (bitsandbytes NF4 4bit)       │
│         VRAM使用: 7.65 GB / 12.88 GB             │
│         KVキャッシュ: TurboQuant 3bit +           │
│                     LinearAttentionLayer         │
└──────────────────────────────────────────────────┘
```

すべてローカルで完結します。外部への通信はありません。

---

## 機能一覧

### 1. Explain — コード解説

エディタで選択したコードを、LLM が解説・問題点指摘します。

**操作方法**
- コードを選択
- 右クリック → **Newton: Explain**
- 右側のパネルにストリーミングで結果が表示される

---

### 2. Fix Error — エラー修正案の生成

エラーが発生しているコードと、そのエラーメッセージを渡すと、修正済みコードを生成します。

**操作方法（自動）**
- エラーのある行にカーソルを置く（または選択する）
- VS Code の診断（赤波線）が検出されている場合、エラーメッセージは自動で取得される
- 右クリック → **Newton: Fix Error**

**操作方法（手動）**
- エラーのあるコードを選択
- 右クリック → **Newton: Fix Error**
- 診断が取得できない場合は入力ボックスが表示されるので、エラーメッセージを貼り付ける

**結果パネルの操作**
- `Show Diff` ボタン: VS Code 標準の diff エディタで修正前後を比較表示
- `Apply` ボタン: 選択範囲をLLMの出力コードで上書き

---

### 3. Generate — コード生成

日本語の仕様・要件からコードを生成します。

**操作方法**
- コマンドパレット (`Ctrl+Shift+P`) → **Newton: Generate**
- テキストボックスに日本語で仕様を入力

---

### 4. Generate Tests — テスト生成

選択した関数・クラスの pytest ユニットテストを生成します。正常系・境界値・エラー系を網羅します。

**操作方法**
- テストを生成したいコードを選択
- 右クリック → **Newton: Generate Tests**

---

### 5. Add Docstring — ドキュメント生成

選択した関数・クラスに Google-style docstring（Args / Returns / Raises 付き）を追加します。

**操作方法**
- docstring を追加したい関数・クラスを選択
- 右クリック → **Newton: Add Docstring**
- 結果パネルの `Apply` ボタンで元のコードに上書き

---

### 6. Generate Commit Message — コミットメッセージ生成

`git diff --staged` の内容から日本語コミットメッセージを自動生成して SCM 入力欄に反映します。  
ステージ済み差分がない場合は `git diff` 全体にフォールバックします。

**操作方法**
- SCM サイドバーのタイトルバー → **Newton: Generate Commit Message**（アイコン）
- またはコマンドパレット → **Newton: Generate Commit Message**

---

### 7. Open Chat — チャットパネル

コードやファイルを添付して自由に質問できるチャットパネルです。マルチターン会話に対応します。

**操作方法**
- コマンドパレット → **Newton: Open Chat**
- またはステータスバーの `● Newton` をクリック

**添付機能**
- 📎ボタン: 選択中のエディタコードをチャットに添付
- 📂ボタン: ファイルまたはフォルダをピッカーで選択して添付
- エクスプローラー右クリック → **Newton Chat に添付**

---

### 8. ステータスバー — サーバー稼働状態の確認

VS Code 右下のステータスバーに常時表示されます。

| 表示 | 意味 |
|------|------|
| `⟳ Newton` | 起動中・確認中 |
| `● Newton 7.65/12.88GB` | サーバー稼働中・VRAM使用量 |
| `○ Newton (loading)` | サーバー起動中だがモデルロード待ち |
| `⊘ Newton (offline)` | サーバーに接続できない |

---

## 起動方法

### サーバーの起動

Newton は**サーバーを先に起動**してから VS Code 拡張を使う必要があります。

```powershell
# ダブルクリックで起動（推奨）
start_server.bat

# または手動起動（PowerShell）
$env:HF_TOKEN = "hf_xxxxxxxxxxxx"   # HuggingFace トークン（初回のみ必要）
python run_server.py
```

初回起動時はモデルのダウンロードが発生します（約5GB）。  
以降はキャッシュから読み込むため、起動まで15〜30秒程度かかります。

サーバーが準備できると以下のログが出ます:
```
[Model] Ready. VRAM allocated: 7.65 GB / reserved: 7.81 GB
INFO:     Uvicorn running on http://127.0.0.1:8000
```

---

## ディレクトリ構成

```
newton/
│
│  # サーバー関連
├── run_server.py            サーバー起動スクリプト
├── start_server.bat         Windows バッチ起動スクリプト
├── test_server.py           動作確認スクリプト
├── requirements.txt         Python 依存パッケージ
│
├── server/
│   ├── main.py              FastAPI エントリーポイント・全エンドポイント定義
│   ├── model.py             Qwen3.5-9B のロード・ストリーミング推論
│   ├── prompts.py           各エンドポイント用のプロンプトビルダー
│   └── context.py           ファイルコンテキスト取得・import依存解析・フォルダ収集
│
│  # VS Code 拡張関連
└── newton-agent/
    ├── package.json         拡張マニフェスト・コマンド定義・メニュー定義
    ├── tsconfig.json        TypeScript 設定
    └── src/
        ├── extension.ts     activate / コマンド登録 / ステータスバー / ヘルスポーリング
        ├── panel.ts         チャットパネル (ストリーミング受信・Diff・Apply)
        ├── editorContext.ts エディタから選択テキスト・言語・診断エラーを取得
        └── diffProvider.ts  newton-diff:// スキームの TextDocumentContentProvider
```

---

## API リファレンス

サーバーは `http://localhost:8000` で動作します。  
Swagger UI: `http://localhost:8000/docs`

### POST /analyze

選択したコードの解説・問題点の指摘を返します。

```json
{
  "code": "def foo(x):\n    return x/0",
  "language": "python",
  "question": ""
}
```

レスポンス: SSE ストリーム (`data: <token>\n\n` ... `data: [DONE]\n\n`)

---

### POST /fix

エラーメッセージをもとに修正済みコードを生成します。

```json
{
  "code": "result = 1 / 0",
  "language": "python",
  "error": "ZeroDivisionError: division by zero",
  "file_path": "C:/myproject/calc.py",
  "focus_line": 3
}
```

レスポンス: SSE ストリーム

---

### POST /generate

日本語の仕様説明からコードを生成します。

```json
{
  "spec": "CSVを読み込んで列ごとの平均値を返す関数",
  "language": "python"
}
```

レスポンス: SSE ストリーム

---

### POST /commit

`git diff` のテキストから日本語のコミットメッセージを生成します。

```json
{
  "diff": "diff --git a/main.py b/main.py\n..."
}
```

レスポンス:
```json
{ "message": "ユーザー認証処理にJWTトークン検証を追加" }
```

---

### POST /chat

`mode` パラメータで動作が変わる汎用チャットエンドポイント。

```json
{
  "message": "この関数を最適化してほしい",
  "history": [],
  "code": "def slow_func(): ...",
  "language": "python",
  "mode": "chat",
  "stream": true
}
```

`mode` の種類: `chat` / `analyze` / `fix` / `generate` / `test` / `document`

---

### GET /health

サーバーの稼働状態と VRAM 使用量を返します。

```json
{
  "status": "ok",
  "model_loaded": true,
  "vram_used_gb": 7.65,
  "vram_total_gb": 12.88
}
```

---

## 設定項目

VS Code の設定 (`settings.json`) から変更できます。

| 設定キー | デフォルト | 説明 |
|---------|-----------|------|
| `newtonAgent.serverUrl` | `http://localhost:8000` | サーバーの URL |

---

## 技術構成詳細

### モデル

| 項目 | 内容 |
|------|------|
| ベースモデル | Qwen/Qwen3.5-9B |
| 量子化方式 | bitsandbytes NF4 4bit |
| VRAM 使用量 | 約 7.65 GB |
| KVキャッシュ | TurboQuant 3bit (full_attention) + LinearAttentionLayer (linear_attention) |
| 推論デバイス | CUDA (cuda:0 に全レイヤー固定) |
| ストリーミング | TextIteratorStreamer + 別スレッドで生成 |

`device_map="auto"` ではなく `{"": 0}` を使う理由: `auto` だと bitsandbytes が非量子化レイヤーを CPU に送り、互換性エラーが発生するため。

### サーバー

- FastAPI + uvicorn (ASGI)
- LLM のストリーミング生成は Server-Sent Events (SSE) で拡張に送信
- CORS は全オリジン許可（localhost のみで動かすため）

### VS Code 拡張

- TypeScript + VS Code Extension API
- サーバーとの通信は Node.js 標準の `http` モジュールで SSE を受信
- WebviewPanel 内でトークンを逐次レンダリング
- diff 表示は `newton-diff://` スキームの TextDocumentContentProvider + `vscode.diff` コマンド
- ステータスバーは 30 秒ごとに `/health` をポーリング

---

## 現在の制限事項

- **複数ファイルの同時編集には対応しない**: 操作対象は選択範囲または現在のファイルのみ
- **LLM がファイルを直接書き換えることはない**: Fix / Apply 系の結果は必ずユーザーが確認して適用する
- **コンテキスト長の制限**: 大きなファイルはサーバー側で 6,000 文字に切り詰められる
- **サーバーの起動が必要**: 拡張を使う前に `run_server.py` を別ターミナルで起動しておく必要がある
- **Windows 専用**: 起動スクリプトや設定が Windows (PowerShell) 前提

---

## トラブルシューティング

### `ModuleNotFoundError: No module named 'uvicorn'`
VS Code がシステムの Python を使っています。  
→ `Ctrl+Shift+P` → **Python: Select Interpreter** → `venv\Scripts\python.exe` を選択

### ステータスバーが `⊘ Newton (offline)`
サーバーが起動していません。  
→ `run_server.py` を実行してください。

### Fix Error でエラーが自動取得されない
VS Code の言語サーバー（Pylance 等）がエラーを診断としてまだ報告していない場合があります。  
→ 入力ボックスにエラーメッセージを手で貼り付けてください。

### Show Diff が表示されない
LLM の応答にコードブロック（` ``` `）が含まれていない場合はボタンが表示されません。  
→ もう一度実行してください。
