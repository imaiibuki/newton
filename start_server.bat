@echo off
chcp 65001 > nul
title Newton Server

echo ============================================
echo  Newton Inference Server
echo ============================================
echo.

cd /d "%~dp0"

:: HF_TOKEN が未設定の場合は警告のみ（設定済みならそのまま使用）
if "%HF_TOKEN%"=="" (
    echo [WARNING] HF_TOKEN が設定されていません。
    echo           レート制限が適用される場合があります。
    echo.
)

echo [Newton] サーバーを起動しています...
echo [Newton] 初回起動はモデルのロードに約15秒かかります。
echo [Newton] 停止するには Ctrl+C を押してください。
echo.

python run_server.py

echo.
echo [Newton] サーバーが停止しました。
pause
