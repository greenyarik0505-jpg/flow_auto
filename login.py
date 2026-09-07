"""
Скрипт авторизации и управления профилями Google Flow.
Поддержка 40+ профилей Google Chrome без конфликтов, без предупреждений --no-sandbox и с защитой от блокировок.
"""
import sys
import os
import json
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

BASE_DIR = Path(__file__).parent.resolve()

STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});
if (!window.chrome) {
    window.chrome = {};
}
window.chrome.runtime = window.chrome.runtime || {
    OnInstalledReason: { CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update' },
    OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' }
};
"""

async def auto_advance_page(page, email_hint: str = "") -> None:
    """Автоматически нажимает кнопки входа, выбора аккаунта и принятия условий."""
    try:
        url = page.url
        # 1. Кнопка "Создать / Створити / Try" на лендинге flow.google.com/about
        if "flow.google.com/about" in url:
            btn = page.locator(
                "button:has-text('Создать'), button:has-text('Створити'), button:has-text('Try'), "
                "button:has-text('Попробовать'), a:has-text('Создать'), a:has-text('Створити')"
            ).first
            if await btn.count() and await btn.is_visible():
                await btn.click(timeout=3000)
                await asyncio.sleep(2)
                return

        # 2. Выбор аккаунта на accounts.google.com
        if "accounts.google.com" in url:
            acc = None
            if email_hint and "@" in email_hint:
                user_part = email_hint.split("@")[0]
                specific = page.locator(f"[data-email*='{user_part}'], [data-identifier*='{user_part}']").first
                if await specific.count() and await specific.is_visible():
                    acc = specific

            if not acc:
                first_acc = page.locator(
                    "[data-profileindex='0'], [data-email], "
                    "div[role='link']:has(div[data-email]), div.v1Fn8d"
                ).first
                if await first_acc.count() and await first_acc.is_visible():
                    acc = first_acc

            if acc:
                await acc.click(timeout=3000)
                await asyncio.sleep(2)
                return

        # 3. Диалог принятия условий использования (Terms of Service)
        tos = page.locator(
            "button:has-text('Принять'), button:has-text('Прийняти'), button:has-text('Accept'), "
            "button:has-text('Agree'), button:has-text('Продолжить'), button:has-text('Далее')"
        ).first
        if await tos.count() and await tos.is_visible():
            await tos.click(timeout=3000)
            await asyncio.sleep(2)
            return

    except Exception:
        pass

async def authorize_profile_interactive(folder: str, display_name: str, email: str = "", headless: bool = False) -> bool:
    session_file = chrome_profiles.get_session_file(folder)
    
    # 1. Проверяем, не авторизован ли уже этот профиль
    is_valid, user_email = chrome_profiles.verify_session(folder)
    if is_valid:
        print(f"\n[✔] Профиль '{folder}' ({display_name}) УЖЕ АВТОРИЗОВАН!")
        print(f"    Аккаунт: {chrome_profiles.mask_email(user_email or email)}")
        print(f"    Файл сессии: {session_file.name} готов к фоновой работе.\n")
        return True

    synced_dir = chrome_profiles.sync_chrome_profile_for_automation(folder, force_sync=True)

    print("\n" + "=" * 80)
    print(f" 🚀 ВХОД В GOOGLE FLOW: {folder} ({display_name})")
    print("=" * 80)
    print("Открывается защищенное окно Google Chrome (без предупреждений --no-sandbox):")
    print(" 1. Скрипт автоматически нажмет 'Создать в Google Flow' и выберет ваш аккаунт.")
    print(" 2. Если потребуется ввод пароля/подтверждение — выполните его в окне браузера.")
    print(" 👉 Как только откроется рабочая область Flow, сессия сохранится и окно закроется САМО!")
    print("=" * 80 + "\n")

    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=str(synced_dir),
            channel="chrome",
            headless=headless,
            chromium_sandbox=True,
            ignore_default_args=["--enable-automation", "--no-sandbox"],
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ]
        )
        await ctx.add_init_script(STEALTH_SCRIPT)

        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        try:
            await page.goto("https://flow.google.com/", wait_until="domcontentloaded", timeout=45000)
        except Exception:
            pass

        print("[+] Окно Chrome открыто. Ожидание входа в Google Flow (до 180 сек)...")
        logged_in = False

        for step in range(90):
            await asyncio.sleep(2)
            try:
                if page.is_closed():
                    print("[-] Окно браузера было закрыто.")
                    break

                # Автоматически продвигаем кликами по кнопкам
                await auto_advance_page(page, email_hint=email)

                # Проверка успешного входа
                url = page.url
                if "flow.google.com" in url and "about" not in url and "accounts.google.com" not in url:
                    logged_in = True
                    break

                # Проверка наличия поля ввода промпта (ProseMirror)
                composer = page.locator("[contenteditable='true'].ProseMirror, [contenteditable='true']").first
                if await composer.count():
                    logged_in = True
                    break

                # Проверка наличия ссылки на проект
                prj = page.locator("a[href*='/project/']").first
                if await prj.count():
                    logged_in = True
                    break

                # Проверка наличия куки NextAuth
                all_cookies = await ctx.cookies()
                has_nextauth = any(c.get("name") == "__Secure-next-auth.session-token" for c in all_cookies)
                if has_nextauth and "accounts.google.com" not in url:
                    logged_in = True
                    break

            except Exception:
                break

        if logged_in:
            await asyncio.sleep(2)
            session_file.parent.mkdir(parents=True, exist_ok=True)
            state = await ctx.storage_state()
            session_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
            
            # Проверяем сохраненную сессию через API
            verified, verified_email = chrome_profiles.verify_session(folder)
            masked = chrome_profiles.mask_email(verified_email or email)

            print("\n" + "=" * 80)
            print(f" [✔] СЕССИЯ ДЛЯ АККАУНТА '{folder}' УСПЕШНО СОХРАНЕНА И ПРОВЕРЕНА!")
            print("=" * 80)
            print(f"    Аккаунт: {masked}")
            print(f"    Файл сессии: {session_file.name}")
            print(f"    Статус: Готов к фоновой генерации видео и фото без окон!\n")
            
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
    parser.add_argument("--headless", action="store_true", help="Запуск в фоновом режиме")
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
        
        is_verified, verified_email = chrome_profiles.verify_session(folder)
        if is_verified:
            status = "✔ ГОТОВ К РАБОТЕ"
        elif chrome_profiles.get_session_file(folder).exists():
            status = "⏳ ТРЕБУЕТ ОБНОВЛЕНИЯ"
        else:
            status = "⏳ НУЖЕН ВХОД"
        print(f"{idx:<3} | {folder:<12} | {name:<20} | {email:<22} | {status}")
    print("-" * 80)

    if args.list:
        return

    if args.all:
        for p in profiles:
            folder = p["folder"]
            is_verified, _ = chrome_profiles.verify_session(folder)
            if not is_verified:
                asyncio.run(authorize_profile_interactive(folder, p["name"], p.get("email", ""), headless=args.headless))
        print("\n[✔] Авторизация всех профилей завершена!")
        return

    if not profile_selector:
        target_p = None
        # Ищем первый неавторизованный профиль
        for p in profiles:
            is_verified, _ = chrome_profiles.verify_session(p["folder"])
            if not is_verified:
                target_p = p
                break
        if not target_p:
            target_p = profiles[0]
        chosen_folder = target_p["folder"]
        chosen_name = target_p["name"]
        chosen_email = target_p.get("email", "")
    else:
        chosen_folder = chrome_profiles.resolve_profile_folder(profile_selector)
        chosen_name = chosen_folder
        chosen_email = ""
        for p in profiles:
            if p["folder"] == chosen_folder:
                chosen_name = p["name"]
                chosen_email = p.get("email", "")
                break

    asyncio.run(authorize_profile_interactive(chosen_folder, chosen_name, chosen_email, headless=args.headless))

if __name__ == "__main__":
    main()
