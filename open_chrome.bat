@echo off
setlocal
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"
if "%~1"=="" (
    ".venv\Scripts\python.exe" login.py --chrome
) else (
    ".venv\Scripts\python.exe" login.py %1 --chrome
)
pause
