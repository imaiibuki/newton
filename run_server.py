"""
run_server.py - サーバー起動スクリプト
使用方法: python run_server.py

事前に HF_TOKEN 環境変数を設定してください:
  PowerShell: $env:HF_TOKEN = "hf_xxxxxxxxxxxx"
"""

import sys
import os
from pathlib import Path

# --- venv チェック ---
# venv 外の Python で起動された場合、venv の Python で再起動する
VENV_PYTHON = Path(__file__).parent / "venv" / "Scripts" / "python.exe"
if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    print(f"[run_server] Switching to venv Python: {VENV_PYTHON}")
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)
    # execv はここより先に進まない

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "server.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,  # モデルロード後のreloadは重いのでFalse
        log_level="info",
    )
