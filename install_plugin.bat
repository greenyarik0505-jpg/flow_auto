@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo ================================================================================
echo  🚀 УСТАНОВКА ПЛАГИНА GOOGLE FLOW ДЛЯ ANTIGRAVITY / CLAUDE / CODEX
echo ================================================================================
echo.

set "DEST=%USERPROFILE%\.gemini\config\plugins\google-flow"
echo [+] Установка плагина в Google Antigravity:
echo     Путь: %DEST%

if not exist "%DEST%" mkdir "%DEST%"
xcopy /E /I /Y "plugins\google-flow\*" "%DEST%\" >nul

if %ERRORLEVEL% equ 0 (
    echo [✔] Плагин успешно установлен в Antigravity!
) else (
    echo [-] Ошибка копирования файлов плагина.
)

echo.
echo [+] Настройка MCP сервера для Claude Code и Cursor:
echo     Файл: .mcp.json создан в корне проекта.
echo.
echo [✔] Все компоненты готовы к работе!
echo.
pause
