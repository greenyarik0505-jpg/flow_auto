@echo off
setlocal
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"
if "%~1"=="" (
    echo Использование: generate_image.bat "Ваш текстовый промпт" [--model nano-pro] [--aspect 16:9] [-n 1]
    echo.
    echo Примеры:
    echo   generate_image.bat "A beautiful futuristic cyber city at sunset"
    echo   generate_image.bat "Portrait of a cyber cat" --model image4 --aspect 1:1 -n 4
    exit /b 1
)
".venv\Scripts\python.exe" generate_image.py %*
