@echo off
setlocal
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"
if "%~1"=="" (
    echo Usage: generate.bat "Your text prompt" [--model omni-flash] [--aspect 16:9] [--duration 10]
    exit /b 1
)
".venv\Scripts\python.exe" generate_video.py %*
