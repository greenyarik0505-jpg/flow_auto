"""
Direct automation engine for Google Flow (flow.google.com).
Handles autonomous generation and downloading of Photos (Imagen 4 / Nano) and Videos (Gemini Omni / Veo).
"""
import os
import sys
import time
import base64
import asyncio
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import chrome_profiles

def get_automation_profile(profile_selector: Optional[str] = None) -> tuple[Path, str]:
    """
    Разрешает и синхронизирует профиль Google Chrome для автоматизации без блокировок.
    Возвращает (путь_к_изолированному_профилю, имя_профиля_chrome).
    """
    chrome_profiles_list = chrome_profiles.get_all_chrome_profiles()
    if chrome_profiles_list:
        chosen_folder = chrome_profiles.resolve_profile_folder(profile_selector)
        name = chosen_folder
        for p in chrome_profiles_list:
            if p["folder"] == chosen_folder:
                name = f"{chosen_folder} ({p['name']})" if p["name"] != chosen_folder else chosen_folder
                break
        
        synced_path = chrome_profiles.sync_chrome_profile_for_automation(chosen_folder)
        return synced_path, name

    # Резервный поиск в старом каталоге ffroliva/gflow-cli
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    base = Path(local_app_data) / "ffroliva" / "gflow-cli"
    if profile_selector:
        p = base / f"profile_{profile_selector}"
        if p.exists():
            return p, p.name
        return base / profile_selector, str(profile_selector)

    if (base / "profile_default").exists():
        return base / "profile_default", "profile_default"
    return base / "profile_default", "profile_default"

async def get_browser_context(pw, profile_path: Path, profile_selector: Optional[str] = None):
    """
    Получает контекст браузера:
    1. Если Chrome запущен на порту 9222 (start_chrome_debug.bat) — подключается через CDP.
    2. Если есть файл сессии .flow_sessions/ — загружает куки сессии.
    3. Иначе запускает изолированный persistent context без конфликтов с Chrome.
    """
    if chrome_profiles.is_cdp_available(port=9222):
        print("    [CDP] Обнаружен запущенный Google Chrome на порту 9222! Подключение...")
        browser = await pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ctx = browser.contexts[0]
        # Проверяем, есть ли уже открытая вкладка Flow
        flow_page = None
        for p in ctx.pages:
            if "flow.google.com" in p.url and "about" not in p.url:
                flow_page = p
                break
        page = flow_page if flow_page else await ctx.new_page()
        return ctx, page, True, browser

    chosen_folder = chrome_profiles.resolve_profile_folder(profile_selector)
    session_file = chrome_profiles.get_session_file(chosen_folder)
    storage_state_arg = str(session_file) if session_file.exists() else None

    if storage_state_arg:
        print(f"    [Сессия] Загрузка сохраненной сессии: {session_file.name}")

    ctx = await pw.chromium.launch_persistent_context(
        user_data_dir=str(profile_path),
        channel="chrome",
        headless=True,
        args=["--disable-blink-features=AutomationControlled"]
    )

    if storage_state_arg:
        try:
            state_data = json.loads(session_file.read_text(encoding="utf-8"))
            if "cookies" in state_data:
                await ctx.add_cookies(state_data["cookies"])
        except Exception:
            pass

    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    return ctx, page, False, None

async def ensure_flow_workspace(page):
    """Обеспечивает переход в рабочую область проекта Google Flow."""
    if "flow.google.com" not in page.url:
        await page.goto("https://flow.google.com/", wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(4)

    # Если находимся на лендинге /about
    if "flow.google.com/about" in page.url:
        start_btn = page.locator("a:has-text('Создать'), a:has-text('Попробовать'), button:has-text('Создать'), button:has-text('Попробовать'), a:has-text('Try'), button:has-text('Try')").first
        if await start_btn.count():
            href = await start_btn.get_attribute("href")
            if href and href.startswith("http"):
                await page.goto(href, wait_until="domcontentloaded", timeout=30000)
            else:
                await start_btn.click()
            await asyncio.sleep(5)

    # Если редиректнуло на логин Google
    if "accounts.google.com" in page.url:
        print("\n[!] Внимание: Требуется авторизация в Google Flow.")
        print("💡 Для мгновенного использования ваших 40 аккаунтов Chrome без повторного ввода:")
        print("   1. Запустите Chrome через: .\\start_chrome_debug.bat")
        print("   2. Либо сохраните сессию аккаунта: .\\capture_session.bat\n")
        raise RuntimeError("Требуется авторизация. Запустите .\\start_chrome_debug.bat или .\\capture_session.bat")

    # Переход в проект если находимся на списке проектов
    composer = page.locator("[contenteditable='true'].ProseMirror, [contenteditable='true']").first
    if not await composer.count():
        prj = page.locator("a[href*='/project/']").first
        if await prj.count():
            await prj.click()
            await asyncio.sleep(4)

async def generate_image_auto(
    prompt: str,
    out_dir: Path,
    model: str = "nano-pro",
    aspect: str = "16:9",
    count: int = 1,
    profile: Optional[str] = None,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    profile_path, profile_display_name = get_automation_profile(profile)
    
    print(f"\n[+] Автоматическая генерация фото через Google Flow...")
    print(f"    Промпт: {prompt}")
    print(f"    Профиль: {profile_display_name}")
    print(f"    Папка : {out_dir}\n")

    saved_files: list[Path] = []

    async with async_playwright() as pw:
        context, page, is_cdp, browser = await get_browser_context(pw, profile_path, profile)
        try:
            await ensure_flow_workspace(page)

            composer = page.locator("[contenteditable='true'].ProseMirror, [contenteditable='true']").first
            await composer.click()
            await composer.fill(prompt)
            await asyncio.sleep(1)

            submit_btn = page.locator("button.generate-icon-button, button[type='submit']").first
            if await submit_btn.count():
                await submit_btn.click()
            else:
                await page.keyboard.press("Enter")

            print("[+] Запрос отправлен в Flow Agent, ожидание рендера...")
            prev_count = await page.locator("img.image, img.image-thumbnail").count()
            for i in range(16):
                await asyncio.sleep(3)
                current_imgs = await page.locator("img.image, img.image-thumbnail").all()
                if len(current_imgs) > prev_count:
                    print(f"[✔] Найдено {len(current_imgs) - prev_count} новых изображений!")
                    for idx, img in enumerate(current_imgs[:count]):
                        src = await img.get_attribute("src")
                        if src and src.startswith("http"):
                            data_url = await page.evaluate("""async (url) => {
                                const res = await fetch(url);
                                const blob = await res.blob();
                                return new Promise((resolve) => {
                                    const reader = new FileReader();
                                    reader.onloadend = () => resolve(reader.result);
                                    reader.readAsDataURL(blob);
                                });
                            }""", src)
                            _, b64 = data_url.split(",", 1)
                            raw = base64.b64decode(b64)
                            timestamp = int(time.time())
                            fn = out_dir / f"image_{timestamp}_{idx+1}.png"
                            fn.write_bytes(raw)
                            saved_files.append(fn)
                            print(f"    [✔] Сохранено: {fn.name} ({len(raw)} байт)")
                    break

        finally:
            if not is_cdp:
                await context.close()

    return saved_files

async def generate_video_auto(
    prompt: str,
    out_dir: Path,
    model: str = "omni-flash",
    aspect: str = "16:9",
    duration: Optional[int] = None,
    profile: Optional[str] = None,
) -> Optional[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    profile_path, profile_display_name = get_automation_profile(profile)

    print(f"\n[+] Автоматическая генерация видео через Google Flow (Omni / Veo)...")
    print(f"    Промпт: {prompt}")
    print(f"    Профиль: {profile_display_name}")
    print(f"    Папка : {out_dir}\n")

    out_file: Optional[Path] = None

    async with async_playwright() as pw:
        context, page, is_cdp, browser = await get_browser_context(pw, profile_path, profile)
        try:
            await ensure_flow_workspace(page)

            add_btn = page.locator("button:has(mat-icon:has-text('add'))").first
            if await add_btn.count():
                await add_btn.click()
                await asyncio.sleep(1)
                scene_item = page.locator("[role='menuitem']").filter(has_text="Нова сцена").first
                if await scene_item.count():
                    await scene_item.click()
                    await asyncio.sleep(3)

            clip = page.locator(".timeline-item, .clip-container, .timeline-clip").first
            if not await clip.count():
                plus_btn = page.locator("button.add-clip-button, button:has(mat-icon:has-text('add_2'))").first
                if await plus_btn.count():
                    await plus_btn.click()
                    await asyncio.sleep(1)
                    asset_card = page.locator(".cdk-overlay-pane button, .cdk-overlay-pane mat-list-item").first
                    if await asset_card.count():
                        await asset_card.click()
                        await asyncio.sleep(2)

            composer = page.locator("[contenteditable='true']").first
            if await composer.count():
                await composer.click()
                await composer.fill(prompt)
                await asyncio.sleep(1)
                submit_btn = page.locator("button.generate-icon-button, button:has(mat-icon:has-text('arrow_forward'))").last
                if await submit_btn.count():
                    await submit_btn.click()
                    print("[+] Запрос на генерацию видео отправлен. Рендеринг клипа...")

            for _ in range(24):
                await asyncio.sleep(5)
                dl_btn = page.locator("button:has(mat-icon:has-text('download'))").first
                if await dl_btn.count():
                    classes = await dl_btn.get_attribute("class") or ""
                    if "disabled" not in classes:
                        print("[✔] Рендеринг завершен! Экспорт и скачивание .mp4...")
                        timestamp = int(time.time())
                        target_mp4 = out_dir / f"video_{timestamp}.mp4"
                        try:
                            async with page.expect_download(timeout=45000) as dl_info:
                                await dl_btn.click()
                            dl = await dl_info.value
                            await dl.save_as(str(target_mp4))
                            print(f"[✔] Видео успешно скачано: {target_mp4.name} ({target_mp4.stat().st_size} байт)")
                            out_file = target_mp4
                            break
                        except Exception:
                            pass
                        break

        finally:
            if not is_cdp:
                await context.close()

    return out_file
