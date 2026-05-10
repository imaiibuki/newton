# Newton — プロジェクト概要

## 概要

クラウドAIに依存せずローカルで動作するコーディングアシスタントです。

オープンソースの Qwen3.5-9B を bitsandbytes NF4 4bit 量子化で VRAM 12GB に収め、
VS Code 拡張機能として動作します。

**設計方針**: Qwen3.5-9Bを**日本語 ↔ コードの翻訳エンジン**として使う。  
LLMはテキスト変換に専念し、ワークフローの組み立ては拡張側が担う。  
エージェント的な自律性・ファイル操作・複数ターン推論は持たせない。

---

## システム構成

```
[VS Code 拡張機能 (TypeScript)]
  - コマンドパレット / コンテキストメニュー
  - 選択範囲・現在ファイル・エラー情報を送信
        |
        | HTTP (localhost:8000)
        v
[推論APIサーバー (Python / FastAPI)]
  - /analyze  コード解析・説明
  - /fix      エラー修正案の生成
  - /generate 日本語仕様 → コード生成
  - /chat     マルチモードチャット
  - /commit   git diff → コミットメッセージ
  - /health   サーバー + VRAM状態
        |
        v
[Qwen3.5-9B (bitsandbytes NF4 4bit量子化)]
  - 単発推論に専念
        |
        v
[NVIDIA GPU (VRAM 12GB)]
```

すべてローカル完結。外部APIへの通信なし。

---

## 採用技術スタック

| 層 | 技術 | 備考 |
|----|------|------|
| モデル | Qwen3.5-9B | HuggingFace 形式 |
| モデル重み量子化 | bitsandbytes NF4 4bit | VRAM ~7.65GB |
| KVキャッシュ | TurboQuant 3bit + LinearAttentionLayer | full_attention / linear_attention 混在対応 |
| 推論バックエンド | PyTorch + CUDA / HuggingFace Transformers | |
| APIサーバー | FastAPI + uvicorn | |
| VS Code拡張 | TypeScript + VS Code Extension API | |

---

## エンドポイント一覧

| エンドポイント | 変換方向 | 内容 |
|---|---|---|
| `/analyze` | コード → 日本語 | コードの説明・問題点の指摘 |
| `/fix` | コード + エラー → コード | エラーメッセージから修正案を生成 |
| `/generate` | 日本語 → コード | 仕様・要件からコード生成 |
| `/chat` | 日本語 ↔ 日本語 | マルチモードチャット（analyze / fix / generate / test / document） |
| `/commit` | git diff → 日本語 | コミットメッセージ自動生成 |
| `/cancel` | — | 進行中の生成を中断 |
| `/health` | — | サーバー稼働状態・VRAM使用量 |

---

## 機能スコープ

### やること
- コード生成: 日本語の仕様・要件からコードを生成
- コード解析: コードの説明・問題点の指摘
- エラー修正: エラーメッセージ + コードを渡して修正案を生成
- テスト生成: 選択コードの pytest ユニットテストを生成
- docstring 生成: 選択コードに Google-style docstring を追加
- コミットメッセージ生成: git diff から日本語コミットメッセージを自動生成
- How-toアドバイス: 「どうやればいい？」系の質問に日本語で回答
- マルチファイルコンテキスト: import 解析・フォルダ添付で複数ファイルをまとめてコンテキストに渡す

### やらないこと
- プロジェクト全体の自律的な把握・編集
- 複数ファイルにまたがるReActループ
- LLMによるファイルの直接書き込み（提案のみ、適用はユーザー操作）

---

## ハードウェア制約

| 項目 | 詳細 |
|------|------|
| GPU | RTX 4070 SUPER |
| VRAM | 12GB |
| 採用モデル | Qwen3.5-9B |
| 重み量子化後VRAM | 7.65GB (bitsandbytes NF4 4bit) |
| KVキャッシュ用余裕 | 約3〜4GB |

VRAM の目安（12GB 環境）:

| 入力トークン数 | 推定VRAM |
|---|---|
| 2,000 | ~8.7 GB |
| 4,000 | ~9.4 GB |
| 6,000 | ~10.6 GB |
| ~7,700 | ~12.3 GB (上限) |

---

## ディレクトリ構成

```
newton/
├── run_server.py            サーバー起動スクリプト
├── start_server.bat         Windows バッチ起動スクリプト
├── requirements.txt         Python 依存パッケージ
├── server/
│   ├── main.py              FastAPI エントリーポイント
│   ├── model.py             LLM ロード・推論
│   ├── prompts.py           プロンプトビルダー
│   └── context.py           ファイルコンテキスト・import依存解析・フォルダ収集
└── newton-agent/            VS Code拡張
    ├── src/
    │   ├── extension.ts     コマンド登録・ステータスバー
    │   ├── editorContext.ts 選択テキスト・言語・診断エラー・workspaceRoot 取得
    │   ├── diffProvider.ts  newton-diff:// スキームの diff プロバイダ
    │   └── panel.ts         チャットパネル（WebviewUI・SSE・コンテキスト添付）
    └── package.json
```
