# Newton — ローカル完結型コーディングアシスタント 仕様書

> バージョン: 0.1.0  
> 最終更新: 2026-04-15

---

## 目次

1. [概要](#1-概要)
2. [システム構成](#2-システム構成)
3. [動作環境・依存関係](#3-動作環境依存関係)
4. [ディレクトリ構成](#4-ディレクトリ構成)
5. [推論サーバー仕様](#5-推論サーバー仕様)
   - 5.1 APIエンドポイント一覧
   - 5.2 各エンドポイント詳細
   - 5.3 SSEストリーミング形式
6. [モデル・推論エンジン仕様](#6-モデル推論エンジン仕様)
7. [コンテキスト収集仕様](#7-コンテキスト収集仕様)
8. [VS Code拡張機能仕様](#8-vs-code拡張機能仕様)
9. [プロンプト設計](#9-プロンプト設計)
10. [起動方法](#10-起動方法)
11. [VRAM使用量の目安](#11-vram使用量の目安)
12. [既知の制限事項](#12-既知の制限事項)

---

## 1. 概要

Newton は、クラウドAIサービスに依存せずローカル環境でPythonコーディングを支援するツールです。

```
ユーザー (VS Code)
    │  コマンド / チャット
    ▼
newton-agent (VS Code拡張機能)
    │  HTTP (localhost:8000)
    ▼
Newton Server (FastAPI + Qwen3.5-9B)
    │  推論
    ▼
Qwen3.5-9B (bitsandbytes NF4 4bit量子化)
```

**設計思想**:
- LLMは「日本語 ↔ コード の翻訳エンジン」として使う
- LLMはテキスト変換に専念し、ファイル操作・ツール呼び出しは行わない
- ワークフロー制御はVS Code拡張側が担う

---

## 2. システム構成

| コンポーネント | 技術 | 役割 |
|---|---|---|
| 推論サーバー | FastAPI + uvicorn | HTTPエンドポイント・SSEストリーミング |
| 推論エンジン | transformers + bitsandbytes | モデルロード・テキスト生成 |
| コンテキスト収集 | Python AST | import解析・依存ファイル収集 |
| VS Code拡張 | TypeScript + VS Code API | UIコマンド・チャットパネル・Diff表示 |

---

## 3. 動作環境・依存関係

### ハードウェア要件

| 項目 | 最小 | 推奨 |
|---|---|---|
| GPU VRAM | 10 GB | 12 GB以上 |
| GPU | CUDA対応 (Compute 8.9+) | RTX 40xxシリーズ (Ada Lovelace) |
| RAM | 16 GB | 32 GB |
| OS | Windows 10/11 | Windows 11 |

> RTX 4070 SUPER (12GB) で動作確認済み。VRAM待機時 ~7.65 GB 消費。

### Pythonパッケージ

```
torch==2.6.0+cu124
torchvision==0.21.0+cu124
transformers==5.5.0
accelerate==1.13.0
bitsandbytes==0.49.2
fastapi==0.135.3
uvicorn[standard]
pydantic
requests
turboquant==0.2.0
```

> `turboquant` は `turboquant.cache` の `TurboQuantLayer` のみ使用。  
> `turboquant.hf_cache` および `turboquant.transformers_integration` は `TurboQuantProd` を要求するため使用不可。

### Node.js / VS Code拡張ビルド要件

```
Node.js >= 18
TypeScript >= 5.4
@types/vscode ^1.90.0
@vscode/vsce (パッケージング時)
```

---

## 4. ディレクトリ構成

```
newton/
├── server/
│   ├── main.py          # FastAPIアプリ・エンドポイント定義
│   ├── model.py         # LLMエンジン（モデルロード・推論・キャッシュ）
│   ├── prompts.py       # プロンプトビルダー
│   └── context.py       # ファイルコンテキスト収集・import解析
├── newton-agent/        # VS Code拡張機能
│   ├── src/
│   │   ├── extension.ts     # コマンド登録・ステータスバー
│   │   ├── panel.ts         # チャットパネルWebview
│   │   ├── editorContext.ts # エディタ状態取得
│   │   └── diffProvider.ts  # Diff表示プロバイダー
│   └── package.json
├── run_server.py        # サーバー起動スクリプト（venv自動切り替え付き）
├── start_server.bat     # ダブルクリックで起動できるバッチファイル
└── requirements.txt     # Pythonパッケージ一覧
```

---

## 5. 推論サーバー仕様

### 5.1 APIエンドポイント一覧

| メソッド | パス | 説明 | レスポンス形式 |
|---|---|---|---|
| GET | `/health` | サーバー・VRAM状態確認 | JSON |
| GET | `/models` | ロード済みモデル情報 | JSON |
| POST | `/analyze` | コード解析・説明 | SSEストリーミング |
| POST | `/fix` | エラー修正 | SSEストリーミング |
| POST | `/generate` | 仕様からコード生成 | SSEストリーミング |
| POST | `/commit` | git diff → コミットメッセージ | JSON |
| POST | `/chat` | マルチモードチャット | SSEストリーミング / JSON |
| POST | `/cancel` | 生成の中断 | JSON |

### 5.2 各エンドポイント詳細

#### `GET /health`

サーバー状態とVRAM使用量を返す。VS Code拡張が30秒ごとにポーリングする。

**レスポンス例:**
```json
{
  "status": "ok",
  "model_loaded": true,
  "vram_used_gb": 7.65,
  "vram_total_gb": 12.28,
  "vram_allocated_gb": 7.65,
  "vram_reserved_gb": 8.10
}
```

---

#### `POST /analyze`

コードの解析・説明を返す。

**リクエスト:**
```json
{
  "code": "def foo(): ...",
  "file_path": "C:/project/main.py",
  "language": "python",
  "question": "この関数の計算量は？",
  "workspace_root": "C:/project",
  "max_new_tokens": 3072
}
```

- `code` と `file_path` はどちらかが必須（両方指定した場合は `file_path` を優先）
- `workspace_root` を指定すると依存ファイルを自動収集してコンテキストに追加

---

#### `POST /fix`

エラーを受け取り、修正済みコードを返す。

**リクエスト:**
```json
{
  "code": "def foo():\n  retrun 1",
  "language": "python",
  "error": "SyntaxError: invalid syntax",
  "file_path": "C:/project/main.py",
  "focus_line": 2,
  "workspace_root": "C:/project",
  "max_new_tokens": 3072
}
```

- `focus_line` を指定すると、その前後200行のみをコンテキストとして使用する

---

#### `POST /generate`

日本語の仕様説明からコードを生成する。

**リクエスト:**
```json
{
  "spec": "CSVを読み込んで列ごとの平均値を返す関数",
  "language": "python",
  "max_new_tokens": 3072
}
```

---

#### `POST /commit`

`git diff` のテキストから日本語のコミットメッセージを生成する。ストリーミングなし、一括レスポンス。

**リクエスト:**
```json
{
  "diff": "diff --git a/main.py b/main.py\n...",
  "max_new_tokens": 256
}
```

**レスポンス:**
```json
{
  "message": "ユーザー認証処理にJWTトークン検証を追加"
}
```

---

#### `POST /chat`

`mode` パラメータで動作が変わる汎用チャットエンドポイント。

**リクエスト:**
```json
{
  "message": "この関数を最適化してほしい",
  "history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "code": "def slow_func(): ...",
  "language": "python",
  "errors": ["TypeError: ..."],
  "file_path": "C:/project/main.py",
  "folder_path": "",
  "workspace_root": "C:/project",
  "mode": "chat",
  "max_new_tokens": 3072,
  "stream": true
}
```

**`mode` の種類:**

| mode | 動作 | 特記事項 |
|---|---|---|
| `chat` | 会話型アシスタント | 履歴・コードコンテキスト・依存ファイルを含む |
| `analyze` | コード解析 | `analyze` エンドポイントと同等 |
| `fix` | エラー修正 | `fix` エンドポイントと同等 |
| `generate` | コード生成 | `generate` エンドポイントと同等 |
| `test` | pytestテスト生成 | 正常系・境界値・エラー系を網羅 |
| `document` | docstring追加 | Google-style、Args/Returns/Raises付き |

コンテキスト収集の優先順位:
1. `folder_path` が指定 → フォルダ全体を収集
2. `file_path` + `workspace_root` → import依存解析で収集
3. どちらもなし → コンテキストなし

---

#### `POST /cancel`

進行中の生成を中断する。`StoppingCriteria` を介してバックグラウンドスレッドに中断信号を送る。

**レスポンス:**
```json
{"status": "cancel requested"}
```

### 5.3 SSEストリーミング形式

レスポンスは `text/event-stream` 形式。各トークンが1行ずつ送出される。

```
data: "def "
data: "foo"
data: "():"
data: [DEPS]["server/model.py", "server/context.py"]
data: [DONE]
```

- `[DEPS]` イベント: 依存ファイルが収集された場合、トークン送出前に送られる。JSON配列でファイルパスを列挙
- `[DONE]` イベント: 生成完了を示す終端マーカー
- エラー発生時: `[ERROR] エラーメッセージ` 形式のトークンが yield される

---

## 6. モデル・推論エンジン仕様

### モデル構成

| 項目 | 内容 |
|---|---|
| モデル | Qwen/Qwen3.5-9B (HuggingFace) |
| 量子化 | bitsandbytes NF4 4bit + double quantization |
| 演算精度 | bfloat16 |
| アテンション | SDPA (PyTorch 2.0組み込み) / flash_attention_2 (flash-attn があれば自動昇格) |
| デバイス | cuda:0 (全レイヤー固定) |
| VRAM (待機時) | ~7.65 GB |

### Qwen3.5 アーキテクチャ

Qwen3.5 は `linear_attention × 3 + full_attention × 1` を8回繰り返す**32層混在アーキテクチャ**。

| レイヤー種別 | 層数 | キャッシュ実装 |
|---|---|---|
| `linear_attention` | 24層 | `LinearAttentionLayer` (HF標準) |
| `full_attention` | 8層 | `TurboQuantLayer(bits=3)` (3bit KV圧縮) |

```python
# _build_hybrid_cache() が構築するキャッシュ
from transformers.cache_utils import DynamicCache, LinearAttentionLayer
from turboquant.cache import TurboQuantLayer

cache = DynamicCache(config=model.config)
for i, layer_type in enumerate(layer_types):
    if layer_type == 'linear_attention':
        cache.layers[i] = LinearAttentionLayer()
    else:
        cache.layers[i] = TurboQuantLayer(bits=3)
```

> `DynamicCache(config=...)` をそのまま使うと linear_attention が `DynamicLayer` になり `ValueError` が発生するため、レイヤーを手動で差し替える。

### プレフィックスKVキャッシュ

システムプロンプト部分の KV を初回のみ計算し、以降は `copy.deepcopy` で再利用する。

```
初回リクエスト:
  [system] → forward pass → KV_sys キャッシュ保存
  [user] → KV_sys を使って続きから推論

2回目以降:
  同一システムプロンプト → KV_sys の deepcopy を再利用 (forward pass スキップ)
```

- キャッシュキー: システムプロンプト内容の MD5ハッシュ
- トークン境界検証: prefix_ids と full_ids の先頭一致を確認。不一致の場合はキャッシュを使わず通常推論

### 推論パラメータ

| パラメータ | デフォルト値 | 説明 |
|---|---|---|
| `max_new_tokens` | 3072 | 最大生成トークン数 |
| `temperature` | 0.2 | サンプリング温度 |
| `do_sample` | True (temperature>0) | サンプリング有効 |

### 例外処理

| 例外 | 動作 |
|---|---|
| `torch.cuda.OutOfMemoryError` | `[ERROR] VRAM が不足しています...` を yield してストリーム終了 |
| その他の例外 | `[ERROR] 生成中にエラーが発生しました: ...` を yield してストリーム終了 |

> `TextIteratorStreamer(raise_exception=True)` によりバックグラウンドスレッドの例外をメインスレッドに伝播させる。

---

## 7. コンテキスト収集仕様

`server/context.py` が提供する3つの収集機能。

### 7.1 `get_file_context(file_path, focus_line)`

ファイル単体のコンテキストを返す（`/fix` エンドポイント用）。

- 上限: 6,000文字 (超過分は `... (truncated)`)
- `focus_line` を指定すると前後200行のみを返す

### 7.2 `collect_dependency_context(file_path, workspace_root)`

AST でimportを解析し、プロジェクト内の依存ファイルを BFS で収集する。

| 設定値 | デフォルト |
|---|---|
| 探索深さ | 2 |
| 合計文字数上限 | 32,000文字 |
| 追加最小文字数 | 500文字 |

- 標準ライブラリ・サードパーティパッケージは除外
- 各ファイルは `{"path": "相対パス", "content": "ソース"}` 形式で返す

### 7.3 `collect_folder_context(folder_path, workspace_root)`

フォルダ以下のファイルを文字数予算内で収集する。チャットへのフォルダ添付に使用。

**対象拡張子:** `.py` `.ts` `.js` `.json` `.yaml` `.yml` `.toml` `.md` `.txt`

**除外ディレクトリ:** `__pycache__` `.git` `.venv` `venv` `node_modules` `.idea` `.vscode`

| 設定値 | デフォルト |
|---|---|
| 合計文字数上限 | 24,000文字 |
| 1ファイル上限 | 4,000文字 |

優先度: `__init__.py` 最優先 → ファイルサイズ昇順で詰め込む  
先頭にディレクトリツリー構造テキスト (`project_tree.txt`) を付加する。  
`.py` ファイルは予算逼迫時にスケルトン化（関数・クラス本体を `...` に置換）する。

---

## 8. VS Code拡張機能仕様

### 8.1 コマンド一覧

| コマンドID | 表示名 | アクセス方法 | 動作 |
|---|---|---|---|
| `newtonAgent.explain` | Newton: Explain | 右クリック / コマンドパレット | 選択コードを解析・説明 (`mode: analyze`) |
| `newtonAgent.fixError` | Newton: Fix Error | 右クリック / コマンドパレット | エラー修正 (`mode: fix`) |
| `newtonAgent.generate` | Newton: Generate | コマンドパレット | 日本語仕様 → コード生成 (`mode: generate`) |
| `newtonAgent.openChat` | Newton: Open Chat | ステータスバークリック | チャットパネルを開く |
| `newtonAgent.commit` | Newton: Generate Commit Message | SCMタイトルバー / コマンドパレット | git diff → コミットメッセージ |
| `newtonAgent.test` | Newton: Generate Tests | 右クリック / コマンドパレット | 選択コード → pytestテスト生成 (`mode: test`) |
| `newtonAgent.document` | Newton: Add Docstring | 右クリック / コマンドパレット | 選択コード → docstring追加 (`mode: document`) |
| `newtonAgent.attachToChat` | Newton Chatに添付 | エクスプローラー右クリック | ファイル/フォルダをチャットに添付 |

### 8.2 設定項目

| 設定キー | デフォルト値 | 説明 |
|---|---|---|
| `newtonAgent.serverUrl` | `http://localhost:8000` | 推論サーバーのURL |

### 8.3 ステータスバー

右下に Newton サーバーの状態を表示。30秒ごとに `/health` をポーリング。

| 表示 | 意味 |
|---|---|
| `● Newton 7.65/12.28GB` | サーバー稼働中 + VRAM使用量 |
| `○ Newton (loading)` | サーバー起動中 |
| `⊘ Newton (offline)` | サーバー未起動 (オレンジ背景) |

### 8.4 チャットパネル

Webview パネル (`vscode.ViewColumn.Beside`) でチャット UI を提供する。

**主な機能:**
- SSE ストリーミングによるリアルタイムトークン表示
- マルチターン会話 (履歴を保持してサーバーに送信)
- コードブロック自動検出・シンタックスハイライト
- `isFix: true` のリクエストに対し **Diff / Apply ボタン** を表示
  - Diff: VS Code ネイティブの差分エディタで変更点を確認
  - Apply: 選択範囲をLLMの出力コードで上書き
- ファイル・フォルダ添付 (エクスプローラーからドラッグ、またはコマンド)
  - ファイル: コンテキストとしてサーバーへ送信
  - フォルダ: `collect_folder_context` でまとめて送信
- 生成キャンセルボタン (`/cancel` エンドポイントを呼び出し)

### 8.5 コミットメッセージ生成の動作フロー

```
1. git diff --staged を実行
2. 差分がない場合は git diff (全体) にフォールバック
3. POST /commit に diff を送信
4. Gitリポジトリが取得できる場合 → SCM入力欄に直接セット
5. 取得できない場合 → クリップボードにコピー
```

---

## 9. プロンプト設計

すべてのプロンプトは `server/prompts.py` に集約されている。

| 関数 | 用途 | 出力形式 |
|---|---|---|
| `build_generate_messages` | 仕様 → コード | コードブロック + 日本語説明 |
| `build_analyze_messages` | コード → 説明 | 日本語説明・問題点・改善点 |
| `build_fix_messages` | コード + エラー → 修正済みコード | コードブロック + 日本語説明 |
| `build_document_messages` | コード → docstring付きコード | Google-style docstring付きコードブロック |
| `build_test_messages` | コード → pytestテスト | テストコードブロック + 日本語説明 |
| `build_commit_messages` | git diff → コミットメッセージ | 50文字以内の日本語サマリー (+箇条書き) |
| `build_chat_messages` | 汎用Q&A | 日本語回答 + コード例 |

**共通の設計方針:**
- システムプロンプトで出力形式を厳密に指定
- 依存ファイルはユーザーメッセージの先頭に付加 (`--- path ---` + コードブロック形式)
- `enable_thinking=False` を指定してThinkingモードを無効化 (高速化)

---

## 10. 起動方法

### サーバー起動

```bash
# ダブルクリックで起動 (推奨)
start_server.bat

# または手動起動
python run_server.py
```

`run_server.py` は venv が存在する場合、自動的に venv の Python で再起動する。

初回起動時はモデルのロードに **約15〜30秒** かかる。ステータスバーが `● Newton` に変わったら使用可能。

### 拡張機能の更新（コード変更後）

```bash
cd newton-agent
npm run compile
npx @vscode/vsce package --allow-missing-repository
code --install-extension newton-agent-0.1.0.vsix
```

---

## 11. VRAM使用量の目安

`full_attention` 8層のアテンション行列がトークン数の2乗に比例するため、入力が長くなるほどVRAMが増加する。

| 入力トークン数 | アテンション | 合計推定VRAM |
|---|---|---|
| 2,000 | 0.24 GB | 8.7 GB |
| 4,000 | 0.95 GB | 9.4 GB |
| 6,000 | 2.15 GB | 10.6 GB |
| ~7,700 | 3.81 GB | ~12.3 GB (上限) |

- **理論的安全上限**: ~7,700トークン (12GB VRAM環境)
- OOM発生時はCUDA例外でストリームが途切れ、`[ERROR] VRAM が不足しています` が返される
- 推論後に `torch.cuda.empty_cache()` を呼び出し、VRAMを待機状態 (~7.65GB) に戻す

---

## 12. 既知の制限事項

| 制限 | 詳細 |
|---|---|
| Linux 非対応 | `flash-attn` のWindows未対応のため SDPA を使用。Linux環境では flash_attention_2 に自動昇格する |
| トークン上限なし | 上限ガードは削除済み（添付ファイルコンテキストでの誤検知を避けるため）。VRAM超過はOOMエラーとして通知される |
| チャット履歴の永続化なし | チャットパネルを閉じると履歴はリセットされる |
| 同時リクエスト | シングルスレッド推論のため、生成中は他のリクエストが待機する |
| Python専用 | コード生成・解析は主にPythonを想定。他言語は `language` パラメータで対応可能だが精度は未検証 |
