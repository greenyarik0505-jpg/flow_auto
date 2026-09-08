"""
Скрипт авторизации и управления сессиями Google Flow (40+ профилей).
Запускает ваш НАСТОЯЩИЙ профиль Chrome (без режима гостя и без конфликтов)
и сохраняет сессию в .flow_sessions/ для 100% автономной генерации в фоне.
"""
import sys
import os
import re
import json
import asyncio
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

def get_clipboard_text() -> str:
    """Читает текст из буфера обмена Windows через PowerShell."""
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3
        )
        return res.stdout.strip()
    except Exception:
        return ""

def open_real_chrome_profile(folder: str, url: str = "https://flow.google.com/") -> bool:
    """
    Открывает НАСТОЯЩИЙ профиль пользователя в Google Chrome.
    Никакого режима гостя: все сохраненные аккаунты, пароли и закладки на месте.
    """
    chrome_exe = chrome_profiles.find_chrome_executable()
    if not chrome_exe:
        print("[-] Ошибка: Исполняемый файл Google Chrome не найден по стандартным путям.")
        return False
    
    cmd = [str(chrome_exe), f"--profile-directory={folder}", url]
    try:
        subprocess.Popen(cmd)
        return True
    except Exception as e:
        print(f"[-] Ошибка запуска Google Chrome: {e}")
        return False

def save_session_from_token(folder: str, token: str) -> bool:
    """
    Сохраняет сессию Google Flow из токена __Secure-next-auth.session-token
    и проверяет её валидность через официальный API.
    """
    token = token.strip().strip('"').strip("'")
    # Если передали строку вида __Secure-next-auth.session-token=...
    if "=" in token and "__Secure" in token:
        for part in token.split(";"):
            part = part.strip()
            if part.startswith("__Secure-next-auth.session-token="):
                token = part.split("=", 1)[1].strip()
                break

    if not token or len(token) < 20:
        print("[-] Ошибка: Токен слишком короткий или пустой.")
        return False

    session_file = chrome_profiles.get_session_file(folder)
    session_file.parent.mkdir(parents=True, exist_ok=True)
    cookie_entry = {
        "name": "__Secure-next-auth.session-token",
        "value": token,
        "domain": "labs.google",
        "path": "/",
        "expires": -1,
        "httpOnly": True,
        "secure": True,
        "sameSite": "Lax"
    }
    state = {
        "cookies": [cookie_entry],
        "origins": [{"origin": "https://labs.google", "localStorage": []}]
    }
    session_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    
    verified, user_email = chrome_profiles.verify_session(folder)
    if verified:
        print("\n" + "=" * 80)
        print(f" [✔] СЕССИЯ ДЛЯ ПРОФИЛЯ '{folder}' УСПЕШНО СОХРАНЕНА И ПРОВЕРЕНА!")
        print("=" * 80)
        print(f"    Аккаунт: {chrome_profiles.mask_email(user_email)}")
        print(f"    Файл сессии: {session_file.name}")
        print("    Этот профиль готов к 100% фоновой генерации видео и фото!\n")
        return True
    else:
        print(f"\n[!] Токен сохранен в {session_file.name}, но проверка через API вернула ошибку.")
        print("    Убедитесь, что скопировано полное значение куки '__Secure-next-auth.session-token'.\n")
        return False

def authorize_profile_via_real_chrome(folder: str, display_name: str, email: str = "", force: bool = False) -> bool:
    """
    Основной метод авторизации: открывает настоящий профиль Chrome и помогает быстро сохранить сессию.
    """
    session_file = chrome_profiles.get_session_file(folder)
    is_valid, user_email = chrome_profiles.verify_session(folder)

    if is_valid and not force:
        print("\n" + "=" * 80)
        print(f" [✔] Профиль '{folder}' ({display_name}) УЖЕ АВТОРИЗОВАН!")
        print("=" * 80)
        print(f"    Аккаунт: {chrome_profiles.mask_email(user_email or email)}")
        print(f"    Файл сессии: {session_file.name} готов к фоновой генерации.")
        print("    Запуск генерации:")
        print(f'      .\\generate.bat "Ваш промпт" --profile "{folder}"')
        print(f'      .\\generate_image.bat "Ваш промпт" --profile "{folder}"\n')
        
        try:
            ans = input("Хотите обновить сохраненную сессию для этого профиля? (y/N): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            return True
        if ans not in ("y", "yes", "д", "да"):
            return True

    print("\n" + "=" * 80)
    print(f" 🚀 АВТОРИЗАЦИЯ GOOGLE FLOW: {folder} ({display_name})")
    print("=" * 80)
    masked = chrome_profiles.mask_email(email)
    if masked:
        print(f"Аккаунт профиля: {masked}")
    print("[+] Открываем вкладку Google Flow в вашем НАСТОЯЩЕМ Chrome (НЕ режим гостя)...")
    
    open_real_chrome_profile(folder, "https://flow.google.com/")

    print("\n💡 В открывшемся окне Chrome:")
    print("  1. Если требуется, нажмите 'Создать в Google Flow' или выберите ваш аккаунт.")
    print("  2. Скопируйте токен авторизации одним из двух простых способов:")
    print("     -------------------------------------------------------------------------")
    print("     👉 Вариант 1 (В 1 КЛИК через расширение flow_extension):")
    print("        Установите папку flow_extension в chrome://extensions (Режим разработчика),")
    print("        нажмите на значок расширения -> 'Скопировать токен Flow'.")
    print("     -------------------------------------------------------------------------")
    print("     👉 Вариант 2 (Через DevTools F12):")
    print("        В открытой вкладке flow.google.com нажмите F12 -> вкладка 'Application'")
    print("        -> Cookies -> https://labs.google -> значение '__Secure-next-auth.session-token'.")
    print("     -------------------------------------------------------------------------")

    clip = get_clipboard_text()
    if clip and (clip.startswith("ey") or "__Secure-next-auth" in clip) and len(clip) > 30:
        print(f"\n[i] В буфере обмена Windows найден токен Flow ({len(clip)} симв.)!")
        try:
            use_clip = input("Использовать токен из буфера обмена? [Enter = Да, или введите другой]: ").strip()
        except (KeyboardInterrupt, EOFError):
            use_clip = ""
        if not use_clip:
            return save_session_from_token(folder, clip)
        else:
            return save_session_from_token(folder, use_clip)

    print()
    try:
        token = input("Вставьте скопированный токен (или нажмите Enter для отмены): ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nОперация отменена.")
        return False

    if not token:
        print("[-] Токен не введен.")
        return False

    return save_session_from_token(folder, token)

async def auto_advance_page(page, email_hint: str = "") -> None:
    """Вспомогательная функция автокликов для Playwright."""
    try:
        url = page.url
        if "flow.google.com/about" in url:
            btn = page.locator(
                "button:has-text('Создать'), button:has-text('Створити'), button:has-text('Try'), "
                "button:has-text('Попробовать'), a:has-text('Создать'), a:has-text('Створити')"
            ).first
            if await btn.count() and await btn.is_visible():
                await btn.click(timeout=3000)
                await asyncio.sleep(2)
                return

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

async def authorize_profile_automated(folder: str, display_name: str, email: str = "", headless: bool = False) -> bool:
    """Запуск изолированного Playwright контекста для автоматического входа (флаг --automated)."""
    session_file = chrome_profiles.get_session_file(folder)
    is_valid, user_email = chrome_profiles.verify_session(folder)
    if is_valid:
        print(f"\n[✔] Профиль '{folder}' ({display_name}) уже авторизован!")
        return True

    synced_dir = chrome_profiles.sync_chrome_profile_for_automation(folder, force_sync=True)

    print("\n" + "=" * 80)
    print(f" 🚀 АВТОМАТИЧЕСКИЙ ВХОД (PLAYWRIGHT): {folder} ({display_name})")
    print("=" * 80)

    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=str(synced_dir),
            channel="chrome",
            headless=headless,
            chromium_sandbox=True,
            ignore_default_args=["--enable-automation", "--no-sandbox"],
            args=[
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

        print("[+] Браузер открыт. Ожидание входа в Google Flow (до 180 сек)...")
        logged_in = False

        for step in range(90):
            await asyncio.sleep(2)
            try:
                if page.is_closed():
                    break
                await auto_advance_page(page, email_hint=email)
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
            verified, verified_email = chrome_profiles.verify_session(folder)
            masked = chrome_profiles.mask_email(verified_email or email)
            print(f"\n[✔] Сессия успешно сохранена для '{folder}' ({masked})!")
            await ctx.close()
            return True
        else:
            print(f"[-] Не удалось зафиксировать вход для '{folder}'.")
            await ctx.close()
            return False

def main():
    parser = argparse.ArgumentParser(description="Google Flow: Авторизация аккаунтов Chrome (40+ профилей)")
    parser.add_argument("profile", type=str, nargs="?", default=None, help="Номер или имя профиля (например: 2, 'Profile 2')")
    parser.add_argument("token_pos", type=str, nargs="?", default=None, help="Токен сессии (опционально: login.bat 2 <token>)")
    parser.add_argument("--profile", dest="profile_opt", type=str, default=None, help="Имя или номер профиля")
    parser.add_argument("--token", type=str, default=None, help="Вставить готовый токен __Secure-next-auth.session-token напрямую")
    parser.add_argument("--all", action="store_true", help="Авторизовать все доступные профили Chrome по очереди")
    parser.add_argument("--list", action="store_true", help="Только показать статус сессий всех профилей")
    parser.add_argument("--force", action="store_true", help="Принудительно перезаписать сессию, даже если она уже валидна")
    parser.add_argument("--automated", action="store_true", help="Использовать изолированный браузер Playwright вместо реального Chrome")
    parser.add_argument("--headless", action="store_true", help="Фоновый режим для --automated")
    args = parser.parse_args()

    profile_selector = args.profile or args.profile_opt
    direct_token = args.token or args.token_pos

    profiles = chrome_profiles.get_all_chrome_profiles()
    if not profiles:
        print("[-] Профили Chrome не найдены.")
        return

    print("=" * 80)
    print(" 🚀 GOOGLE FLOW: СТАТУС СЕССИЙ АККАУНТОВ (40+ ПРОФИЛЕЙ)")
    print("=" * 80)
    print(f"Каталог данных Chrome: {chrome_profiles.get_chrome_user_data_path()}\n")

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

    # Если профиль не указан, берем первый неавторизованный (или Default)
    if not profile_selector:
        target_p = None
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

    # 1. Если токен передан напрямую аргументом (.\\login.bat 2 <token> или --token <token>)
    if direct_token:
        save_session_from_token(chosen_folder, direct_token)
        return

    # 2. Пакетная авторизация --all
    if args.all:
        for p in profiles:
            folder = p["folder"]
            is_verified, _ = chrome_profiles.verify_session(folder)
            if not is_verified or args.force:
                if args.automated:
                    asyncio.run(authorize_profile_automated(folder, p["name"], p.get("email", ""), headless=args.headless))
                else:
                    authorize_profile_via_real_chrome(folder, p["name"], p.get("email", ""), force=args.force)
        print("\n[✔] Обработка всех профилей завершена!")
        return

    # 3. Одиночная авторизация выбранного профиля
    if args.automated:
        asyncio.run(authorize_profile_automated(chosen_folder, chosen_name, chosen_email, headless=args.headless))
    else:
        authorize_profile_via_real_chrome(chosen_folder, chosen_name, chosen_email, force=args.force)

if __name__ == "__main__":
    main()
