"""
test_server.py - サーバー動作確認スクリプト
使用方法: python test_server.py
（サーバー起動後に別ターミナルで実行）
"""

import requests

BASE_URL = "http://127.0.0.1:8000"


def test_health():
    print("[1] Health check...")
    r = requests.get(f"{BASE_URL}/health")
    data = r.json()
    print(f"    status       : {data['status']}")
    print(f"    model_loaded : {data['model_loaded']}")
    if "vram_used_gb" in data:
        print(f"    VRAM         : {data['vram_used_gb']} / {data['vram_total_gb']} GB")
    assert data["status"] == "ok", "Health check failed"
    print("    OK\n")


def test_models():
    print("[2] Model info...")
    r = requests.get(f"{BASE_URL}/models")
    for k, v in r.json().items():
        print(f"    {k}: {v}")
    print()


def test_analyze():
    print("[3] /analyze (コード解析)...")
    payload = {
        "code": "def fib(n):\n    if n <= 1: return n\n    return fib(n-1) + fib(n-2)",
        "language": "python",
        "question": "このコードが何をしているか説明してください。",
        "max_new_tokens": 256,
    }
    r = requests.post(f"{BASE_URL}/analyze", json=payload, stream=True)
    print("    Response: ", end="", flush=True)
    for line in r.iter_lines():
        if line:
            token = line.decode("utf-8")
            if token.startswith("data: "):
                token = token[6:]
                if token != "[DONE]":
                    print(token, end="", flush=True)
    print("\n    OK\n")


def test_analyze_file():
    print("[4] /analyze (ファイル全体)...")
    payload = {
        "file_path": "server/prompts.py",
        "language": "python",
        "question": "このファイルの役割を一言で説明してください。",
        "max_new_tokens": 128,
    }
    r = requests.post(f"{BASE_URL}/analyze", json=payload, stream=True)
    print("    Response: ", end="", flush=True)
    for line in r.iter_lines():
        if line:
            token = line.decode("utf-8")
            if token.startswith("data: "):
                token = token[6:]
                if token != "[DONE]":
                    print(token, end="", flush=True)
    print("\n    OK\n")


def test_fix():
    print("[5] /fix (エラー修正)...")
    payload = {
        "code": "result = 1 / 0\nprint(result)",
        "language": "python",
        "error": "ZeroDivisionError: division by zero",
        "max_new_tokens": 512,
    }
    r = requests.post(f"{BASE_URL}/fix", json=payload, stream=True)
    print("    Response: ", end="", flush=True)
    for line in r.iter_lines():
        if line:
            token = line.decode("utf-8")
            if token.startswith("data: "):
                token = token[6:]
                if token != "[DONE]":
                    print(token, end="", flush=True)
    print("\n    OK\n")


def test_generate():
    print("[6] /generate (コード生成)...")
    payload = {
        "spec": "リストを受け取って、その中の偶数だけを返す関数を作ってください。",
        "language": "python",
        "max_new_tokens": 512,
    }
    r = requests.post(f"{BASE_URL}/generate", json=payload, stream=True)
    print("    Response: ", end="", flush=True)
    for line in r.iter_lines():
        if line:
            token = line.decode("utf-8")
            if token.startswith("data: "):
                token = token[6:]
                if token != "[DONE]":
                    print(token, end="", flush=True)
    print("\n    OK\n")


def test_chat():
    print("[7] /chat (Q&A)...")
    payload = {
        "message": "Pythonのリスト内包表記とは何ですか？一文で教えてください。",
        "history": [],
        "max_new_tokens": 128,
        "stream": True,
    }
    r = requests.post(f"{BASE_URL}/chat", json=payload, stream=True)
    print("    Response: ", end="", flush=True)
    for line in r.iter_lines():
        if line:
            token = line.decode("utf-8")
            if token.startswith("data: "):
                token = token[6:]
                if token != "[DONE]":
                    print(token, end="", flush=True)
    print("\n    OK\n")


if __name__ == "__main__":
    print("=" * 50)
    print("Newton Server Test")
    print("=" * 50 + "\n")
    try:
        test_health()
        test_models()
        test_analyze()
        test_analyze_file()
        test_fix()
        test_generate()
        test_chat()
        print("All tests passed!")
    except Exception as e:
        print(f"\nError: {e}")
        print("Make sure the server is running: python run_server.py")
