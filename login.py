"""
Скрипт авторизации и управления профилями Google Flow.
Благодаря Zero-Login Sync система автоматически видит все профили Chrome (40+ аккаунтов).
Повторный вход не требуется, если в Google Chrome уже выполнен вход!
"""
import sys
import argparse
import subprocess
from pathlib import Path
import chrome_profiles

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).parent.resolve()
VENV_GFLOW = BASE_DIR / ".venv" / "Scripts" / "gflow.exe"

def get_gflow_bin() -> str:
    if VENV_GFLOW.exists():
        return str(VENV_GFLOW)
    return "gflow"

import json
import asyncio
from playwright.async_api import async_playwright

async def authorize_profile_interactive(folder: str, display_name: str) -> bool:
    synced_dir = chrome_profiles.sync_chrome_profile_for_automation(folder, force_sync=True)
    session_file = chrome_profiles.get_session_file(folder)

    print("\n" + "=" * 80)
    print(f" 🚀 АВТОРИЗАЦИЯ GOOGLE FLOW: {folder} ({display_name})")
    print("=" * 80)
    print("В открывшемся окне браузера:")
    print(" 1. Нажмите 'Войти' / 'Sign in' / 'Попробовать Flow' / 'Try Flow'.")
    print(" 2. Выберите ваш аккаунт Google из списка (1 клик).")
    print(" 👉 Как только вы окажетесь на главной странице Flow, сессия сохранится АВТОМАТИЧЕСКИ!")
    print("=" * 80 + "\n")

    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=str(synced_dir),
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        try:
            await page.goto("https://flow.google.com/", wait_until="domcontentloaded", timeout=45000)
        except Exception:
            pass

        print("[+] Окно открыто. Ожидание входа в Google Flow (до 180 секунд)...")
        logged_in = False
        for _ in range(90):
            await asyncio.sleep(2)
            try:
                if page.is_closed():
                    print("[-] Окно браузера было закрыто пользователем.")
                    break

                url = page.url
                if "flow.google.com" in url and "about" not in url and "accounts.google.com" not in url:
                    logged_in = True
                    break

                composer = page.locator("[contenteditable='true'].ProseMirror, [contenteditable='true']").first
                if await composer.count():
                    logged_in = True
                    break

                prj = page.locator("a[href*='/project/']").first
                if await prj.count():
                    logged_in = True
                    break
            except Exception:
                break

        if logged_in:
            await asyncio.sleep(2)
            state = await ctx.storage_state()
            session_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
            print("\n" + "=" * 80)
            print(f" [✔] СЕССИЯ ДЛЯ АККАУНТА '{folder}' УСПЕШНО СОХРАНЕНА!")
            print("=" * 80)
            print(f" Файл сессии: {session_file.name}")
            print(" Теперь этот аккаунт готов к фоновой генерации без всплывающих окон!\n")
            await ctx.close()
            return True
        else:
            print(f"[-] Не удалось зафиксировать вход для профиля '{folder}'.")
            await ctx.close()
            return False

def main():
    parser = argparse.ArgumentParser(description="Google Flow: Авторизация аккаунтов Chrome (40+ профилей)")
    parser.add_argument("profile", type=str, nargs="?", default=None, help="Номер или имя профиля (например: 2, 'Profile 2')")
    parser.add_argument("--profile", dest="profile_opt", type=str, default=None, help="Имя или номер профиля")
    parser.add_argument("--all", action="store_true", help="Авторизовать все доступные профили Chrome по очереди")
    parser.add_argument("--list", action="store_true", help="Только показать статус сессий всех профилей")
    args = parser.parse_args()

    profile_selector = args.profile or args.profile_opt

    profiles = chrome_profiles.get_all_chrome_profiles()
    if not profiles:
        print("[-] Профили Chrome не найдены.")
        return

    print("=" * 80)
    print(" 🚀 GOOGLE FLOW: СТАТУС СЕССИЙ АККАУНТОВ (40+ ПРОФИЛЕЙ)")
    print("=" * 80)
    print(f"Каталог данных: {chrome_profiles.get_chrome_user_data_path()}\n")

    print(f"{'#':<3} | {'Папка':<12} | {'Имя в Chrome':<20} | {'Email':<22} | {'Сессия Flow'}")
    print("-" * 80)

    for idx, p in enumerate(profiles, start=1):
        folder = p["folder"]
        name = p["name"][:18]
        email = chrome_profiles.mask_email(p["email"]) or "(локальный)"
        if len(email) > 20:
            email = email[:19] + "…"
        s_file = chrome_profiles.get_session_file(folder)
        has_session = s_file.exists()
        status = "✔ ГОТОВ К РАБОТЕ" if has_session else "⏳ НУЖЕН ВХОД (1 клик)"
        print(f"{idx:<3} | {folder:<12} | {name:<20} | {email:<22} | {status}")
    print("-" * 80)

    if args.list:
        return

    if args.all:
        for p in profiles:
            folder = p["folder"]
            s_file = chrome_profiles.get_session_file(folder)
            if not s_file.exists():
                asyncio.run(authorize_profile_interactive(folder, p["name"]))
        print("\n[✔] Авторизация всех профилей завершена!")
        return

    if not profile_selector:
        target_p = None
        for p in profiles:
            s_file = chrome_profiles.get_session_file(p["folder"])
            if not s_file.exists():
                target_p = p
                break
        if not target_p:
            target_p = profiles[0]
        chosen_folder = target_p["folder"]
        chosen_name = target_p["name"]
    else:
        chosen_folder = chrome_profiles.resolve_profile_folder(profile_selector)
        chosen_name = chosen_folder
        for p in profiles:
            if p["folder"] == chosen_folder:
                chosen_name = p["name"]
                break

    asyncio.run(authorize_profile_interactive(chosen_folder, chosen_name))

if __name__ == "__main__":
    main()
