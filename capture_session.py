"""
Утилита захвата авторизованной сессии из запущенного Google Chrome (через порт отладки 9222).
Позволяет сохранить сессию в файл .flow_sessions/ для последующей 100% автономной фоновой работы.
"""
import sys
import asyncio
import argparse
from pathlib import Path
from playwright.async_api import async_playwright
import chrome_profiles

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

async def capture(profile_name: str, port: int = 9222):
    print("=" * 80)
    print(" 🚀 ЗАХВАТ СЕССИИ GOOGLE FLOW ИЗ БРАУЗЕРА")
    print("=" * 80)

    if not chrome_profiles.is_cdp_available(port=port):
        print(f"[-] Google Chrome не запущен с портом отладки {port}.")
        print("Пожалуйста, запустите: .\\start_chrome_debug.bat")
        print("Откройте в Chrome сайт https://flow.google.com и убедитесь, что вы авторизованы.")
        return False

    resolved_folder = chrome_profiles.resolve_profile_folder(profile_name)
    session_file = chrome_profiles.get_session_file(resolved_folder)

    print(f"[+] Подключение к Chrome через порт {port}...")
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        context = browser.contexts[0]

        # Ищем существующую вкладку с flow.google.com или открываем новую
        target_page = None
        for p in context.pages:
            if "flow.google.com" in p.url:
                target_page = p
                break

        if not target_page:
            print("[+] Открываем flow.google.com для проверки авторизации...")
            target_page = await context.new_page()
            await target_page.goto("https://flow.google.com/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

        print(f"[+] Текущая страница: {target_page.url}")
        if "accounts.google.com" in target_page.url:
            print("[!] Вы находитесь на странице входа. Пожалуйста, выполните вход в открывшемся окне Chrome.")
            print("Ожидание входа (до 60 секунд)...")
            for _ in range(20):
                await asyncio.sleep(3)
                if "accounts.google.com" not in target_page.url:
                    break

        # Сохраняем расшифрованное состояние сессии (Cookies + LocalStorage)
        session_file.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(session_file))
        print(f"\n[✔] Сессия успешно сохранена в: {session_file}")
        print(f"Теперь для профиля '{resolved_folder}' генератор может работать полностью в фоне!")
        await browser.close()
        return True

def main():
    parser = argparse.ArgumentParser(description="Захват сессии Google Flow из браузера")
    parser.add_argument("profile", type=str, nargs="?", default="Default", help="Имя или номер профиля (по умолчанию Default)")
    parser.add_argument("--port", type=int, default=9222, help="Порт отладки Chrome (по умолчанию 9222)")
    args = parser.parse_args()

    asyncio.run(capture(args.profile, args.port))

if __name__ == "__main__":
    main()
