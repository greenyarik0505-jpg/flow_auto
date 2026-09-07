@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
echo ================================================================================
echo  🚀 ЗАПУСК GOOGLE CHROME С ПОДДЕРЖКОЙ АВТОМАТИЗАЦИИ (40+ АККАУНТОВ)
echo ================================================================================
echo.
echo Этот скрипт запускает ваш обычный Google Chrome со всеми вашими профилями
echo и активирует локальный порт отладки 9222 для мгновенной генерации без ре-логина.
echo.
echo ВАЖНО: Если Google Chrome сейчас открыт, закройте его перед запуском этого батника!
echo.

set "CHROME_EXE="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    set "CHROME_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
) else if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    set "CHROME_EXE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
) else if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" (
    set "CHROME_EXE=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
)

if "%CHROME_EXE%"=="" (
    echo [-] Google Chrome не найден по стандартным путям!
    pause
    exit /b 1
)

echo Запуск Chrome: "!CHROME_EXE!"...
start "" "!CHROME_EXE!" --remote-debugging-port=9222 %*

echo.
echo [✔] Google Chrome успешно запущен на порту 9222!
echo Теперь вы можете переключаться между любыми из 40 аккаунтов в Chrome,
echo а генератор будет автоматически использовать ваши открытые вкладки:
echo.
echo   .\generate.bat "A futuristic flying car over cyberpunk city"
echo   .\generate_image.bat "A cybernetic dragon in neon forest"
echo.
pause
