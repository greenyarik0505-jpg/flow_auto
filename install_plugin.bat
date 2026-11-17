@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo ================================================================================
echo  Google Flow Plugin Installer for Antigravity / Claude / Codex
echo ================================================================================

set "DEST=%USERPROFILE%\.gemini\config\plugins\google-flow"
echo [+] Installing plugin into Antigravity: %DEST%

if not exist "%DEST%" mkdir "%DEST%"
xcopy /E /I /Y "plugins\google-flow\*" "%DEST%\" >nul

if %ERRORLEVEL% equ 0 (
    echo [OK] Plugin files successfully copied to Antigravity!
) else (
    echo [FAIL] Error copying plugin files.
)

echo.
echo [OK] MCP Server config available at: .mcp.json
echo [OK] All components ready.
pause
