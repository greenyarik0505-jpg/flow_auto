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

QUOTA_KEYWORDS = [
    "0 credits", "0 credit", "no credits", "out of credits", "not enough credits",
    "credit balance", "insufficient credits", "0 кредитов", "0 кредитів",
    "недостаточно кредитов", "не вистачає кредитів", "исчерпан лимит",
    "превышен лимит", "достигнут лимит", "quota exceeded", "resource_exhausted",
    "rate limit", "upgrade plan", "купить кредиты", "підписк", "подписк",
    "you have reached your limit", "limit reached", "try again later"
]

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

async def check_ui_quota_limits(page) -> Optional[str]:
    """
    Проверяет элементы интерфейса Google Flow на наличие признаков исчерпания квоты или кредитов.
    """
    # 1. Проверяем оверлеи, снекбары, алерты
    alerts = page.locator("mat-snack-bar-container, [role='alert'], [role='dialog'], .cdk-overlay-pane, .error-banner, .toast")
    try:
        count = await alerts.count()
        for i in range(min(count, 6)):
            el = alerts.nth(i)
            txt = (await el.inner_text() or "").lower()
            for kw in QUOTA_KEYWORDS:
                if kw in txt:
                    return f"Всплывающее предупреждение: {txt.strip()[:150]}"
    except Exception:
        pass

    # 2. Проверяем счетчик кредитов в интерфейсе
    credits = page.locator("[class*='credit'], [class*='quota'], [aria-label*='credit'], [aria-label*='кредит']")
    try:
        count = await credits.count()
        for i in range(min(count, 6)):
            el = credits.nth(i)
            txt = (await el.inner_text() or "").lower()
            if any(k in txt for k in ["0 credit", "0 credits", "0 кредитов", "0 кредитів", "0 /", "0/"]):
                return f"Нулевой баланс кредитов: {txt.strip()}"
    except Exception:
        pass

    # 3. Проверяем статус кнопки генерации
    btn = page.locator("button.generate-icon-button, button[type='submit']").first
    try:
        if await btn.count():
            classes = await btn.get_attribute("class") or ""
            disabled = await btn.get_attribute("disabled")
            if "mat-button-disabled" in classes or disabled is not None:
                aria = (await btn.get_attribute("aria-label") or "").lower()
                for kw in QUOTA_KEYWORDS:
                    if kw in aria:
                        return f"Кнопка генерации отключена: {aria.strip()}"
    except Exception:
        pass

    return None

def get_automation_profile(
    profile_selector: Optional[str] = None,
    exclude: Optional[set[str]] = None,
) -> tuple[Path, str, str]:
    """
    Разрешает и синхронизирует профиль Google Chrome для автоматизации без блокировок.
    Возвращает (путь_к_изолированному_профилю, имя_для_вывода, папка_профиля_chrome).
    """
    chrome_profiles_list = chrome_profiles.get_all_chrome_profiles()
    if chrome_profiles_list:
        chosen_folder = chrome_profiles.resolve_profile_folder(profile_selector, exclude=exclude)
        name = chosen_folder
        for p in chrome_profiles_list:
            if p["folder"] == chosen_folder:
                name = f"{chosen_folder} ({p['name']})" if p["name"] != chosen_folder else chosen_folder
                break
        
        synced_path = chrome_profiles.sync_chrome_profile_for_automation(chosen_folder)
        return synced_path, name, chosen_folder

    # Резервный поиск в старом каталоге ffroliva/gflow-cli
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    base = Path(local_app_data) / "ffroliva" / "gflow-cli"
    if profile_selector:
        p = base / f"profile_{profile_selector}"
        if p.exists():
            return p, p.name, p.name
        return base / profile_selector, str(profile_selector), str(profile_selector)

    if (base / "profile_default").exists():
        return base / "profile_default", "profile_default", "Default"
    return base / "profile_default", "profile_default", "Default"

async def get_browser_context(pw, profile_path: Path, profile_folder: str = "Default"):
    """
    Запускает изолированный контекст Chromium Playwright.
    Загружает сессию из .flow_sessions/ без блокировки дисковых профилей Chrome (ProcessSingleton).
    """
    session_file = chrome_profiles.get_session_file(profile_folder)
    if not session_file.exists():
        if profile_folder.lower() != "default":
            print(f"\n[-] ОШИБКА: Для профиля '{profile_folder}' не найдена сохраненная сессия Flow!", flush=True)
            print(f"💡 Чтобы авторизовать этот аккаунт, запустите:", flush=True)
            print(f"   .\\login.bat {profile_folder}\n", flush=True)
            raise RuntimeError(f"Сессия Flow для '{profile_folder}' отсутствует. Сначала выполните: .\\login.bat {profile_folder}")
        storage_state_arg = None
    else:
        storage_state_arg = str(session_file)
        print(f"    [Сессия] Загрузка сохраненной сессии: {session_file.name}", flush=True)

    print("    [Браузер] Запуск изолированного контекста Chromium...", flush=True)
    browser = await pw.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-dev-shm-usage",
        ]
    )
    ctx = await browser.new_context(
        storage_state=storage_state_arg,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
    )
    await ctx.add_init_script(STEALTH_SCRIPT)

    # При закрытии контекста закрываем и сам инстанс браузера
    orig_close = ctx.close
    async def close_all():
        try:
            await orig_close()
        finally:
            await browser.close()
    ctx.close = close_all

    page = await ctx.new_page()
    return ctx, page

async def ensure_flow_workspace(page):
    """Обеспечивает переход в рабочую область проекта Google Flow."""
    print("    [Flow] Подключение к flow.google.com...", flush=True)
    if "flow.google.com" not in page.url:
        await page.goto("https://flow.google.com/", wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(2)

    # Закрытие стартовых баннеров/модалок если есть
    for _ in range(2):
        close_btn = page.locator(
            "button:has-text('Почати'), button:has-text('Start'), "
            "button:has-text('Got it'), button:has-text('Зрозуміло'), "
            "button[aria-label='Закрити'], button[aria-label='Close'], button[aria-label='Закрити банер']"
        ).first
        if await close_btn.count():
            try:
                await close_btn.click()
                await asyncio.sleep(1)
            except Exception:
                pass

    if "flow.google.com/about" in page.url or "accounts.google.com" in page.url:
        print("\n[!] Внимание: Требуется разовая авторизация в Google Flow.", flush=True)
        print("💡 Для входа в ваши аккаунты запустите:", flush=True)
        print("   .\\login.bat               (для первого аккаунта)", flush=True)
        print("   .\\login.bat 2             (для второго аккаунта)", flush=True)
        print("   .\\login.bat --all         (для всех аккаунтов по очереди)\n", flush=True)
        raise RuntimeError("Требуется авторизация в Google Flow. Запустите .\\login.bat")

    # Если уже на странице проекта и виден инпут
    composer = page.locator("div.ProseMirror, [contenteditable='true'], [role='textbox']").first
    if await composer.count():
        print("    [Flow] Проект уже открыт и готов к работе.", flush=True)
        return

    print("    [Flow] Переход в проект...", flush=True)
    # Переход в проект из списка проектов
    prj = page.locator("a[href*='/project/']").first
    if await prj.count():
        href = await prj.get_attribute("href") or ""
        clean_href = href.split("/tools")[0]
        if clean_href:
            target_url = clean_href if clean_href.startswith("http") else f"https://flow.google.com{clean_href}"
            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
    else:
        # Если проектов еще нет — нажимаем кнопку создания нового проекта
        new_prj = page.locator("button:has-text('Новий проєкт'), button:has-text('New project'), button:has-text('Start Creating')").first
        if await new_prj.count():
            await new_prj.click()
            await asyncio.sleep(4)

    # Закрываем приветственное модальное окно внутри проекта ("Faster loading...", "Почати")
    modal_btn = page.locator("button:has-text('Почати'), button:has-text('Start'), button:has-text('Зрозуміло'), button:has-text('Got it')").first
    if await modal_btn.count():
        try:
            await modal_btn.click()
            await asyncio.sleep(1)
        except Exception:
            pass

    print("    [Flow] Рабочая область проекта успешно загружена.", flush=True)

async def generate_image_auto(
    prompt: str,
    out_dir: Path,
    model: str = "nano-pro",
    aspect: str = "16:9",
    count: int = 1,
    profile: Optional[str] = None,
    exclude: Optional[set[str]] = None,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    profile_path, profile_display_name, profile_folder = get_automation_profile(profile, exclude=exclude)
    
    print(f"\n[+] Автоматическая генерация фото через Google Flow...", flush=True)
    print(f"    Промпт : {prompt}", flush=True)
    print(f"    Профиль: {profile_display_name}", flush=True)
    print(f"    Папка  : {out_dir}\n", flush=True)

    saved_files: list[Path] = []
    quota_state = {"exhausted": False, "reason": ""}
    captured_from_net: list[tuple[str, bytes]] = []

    async with async_playwright() as pw:
        context, page = await get_browser_context(pw, profile_path, profile_folder)

        async def on_response(resp):
            if resp.status == 429:
                quota_state["exhausted"] = True
                quota_state["reason"] = f"HTTP 429 Too Many Requests (Превышен лимит запросов Flow)"
            elif resp.status == 200 and any(k in resp.url for k in ["flow-content.google/image", "flow.google.com/asb"]):
                try:
                    body = await resp.body()
                    if len(body) > 20000:
                        captured_from_net.append((resp.url, body))
                except Exception:
                    pass

        page.on("response", on_response)

        try:
            await ensure_flow_workspace(page)

            # Проверка лимитов на загруженной странице
            quota_err = await check_ui_quota_limits(page)
            if quota_err or quota_state["exhausted"]:
                reason = quota_err or quota_state["reason"]
                chrome_profiles.mark_profile_exhausted(profile_folder, reason)
                raise chrome_profiles.QuotaExceededError(profile_folder, reason)

            composer = page.locator("div.ProseMirror, [contenteditable='true'], [role='textbox']").first
            try:
                await composer.wait_for(state="visible", timeout=15000)
            except Exception:
                await asyncio.sleep(2)
                composer = page.locator("div.ProseMirror, [contenteditable='true'], [role='textbox']").first

            # Сбрасываем перехваченные картинки, загруженные при открытии страницы проекта
            captured_from_net.clear()

            print(f"    [Flow] Ввод промпта...", flush=True)
            await composer.click()
            await asyncio.sleep(0.3)
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await page.keyboard.type(prompt)
            await asyncio.sleep(0.8)

            # Запоминаем текущие картинки до отправки запроса
            initial_srcs = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('img'))
                    .filter(i => i.src && (i.src.includes('flow-content.google') || i.src.includes('/asb/')))
                    .map(i => i.src);
            }""")
            initial_set = set(initial_srcs)

            submit_btn = page.locator(
                "button.generate-icon-button, button[aria-label*='Start generation'], "
                "button[aria-label*='Почати створення'], button[aria-label*='Start creating'], "
                "button[aria-label*='Generate'], button[aria-label*='Створити'], "
                "button:has-text('arrow_forward'), button[type='submit']"
            ).first

            # Очищаем буфер сетевого перехвата строго перед запуском отправки
            captured_from_net.clear()

            if await submit_btn.count():
                classes = await submit_btn.get_attribute("class") or ""
                disabled = await submit_btn.get_attribute("disabled")
                if "mat-button-disabled" in classes or disabled is not None:
                    # Если кнопка еще заблокирована, пробуем нажать Enter
                    print("    [Flow] Отправка запроса по клавише Enter...", flush=True)
                    await page.keyboard.press("Enter")
                else:
                    print("    [Flow] Отправка запроса...", flush=True)
                    await submit_btn.click()
            else:
                print("    [Flow] Отправка запроса по клавише Enter...", flush=True)
                await page.keyboard.press("Enter")

            await asyncio.sleep(2)
            quota_err = await check_ui_quota_limits(page)
            if quota_err or quota_state["exhausted"]:
                reason = quota_err or quota_state["reason"]
                chrome_profiles.mark_profile_exhausted(profile_folder, reason)
                raise chrome_profiles.QuotaExceededError(profile_folder, reason)

            print("[+] Запрос принят Google Flow! Ожидание рендеринга Imagen 4...", flush=True)

            for i in range(35):
                await asyncio.sleep(3)
                elapsed = (i + 1) * 3
                print(f"    ⏳ Рендеринг изображения... ({elapsed}с)", flush=True)

                if quota_state["exhausted"]:
                    chrome_profiles.mark_profile_exhausted(profile_folder, quota_state["reason"])
                    raise chrome_profiles.QuotaExceededError(profile_folder, quota_state["reason"])
                quota_err = await check_ui_quota_limits(page)
                if quota_err:
                    chrome_profiles.mark_profile_exhausted(profile_folder, quota_err)
                    raise chrome_profiles.QuotaExceededError(profile_folder, quota_err)

                # Способ 1: Прямой перехват из сетевого потока Google Flow
                new_net_images = [(u, b) for (u, b) in captured_from_net if u not in initial_set]
                if new_net_images:
                    await asyncio.sleep(1) # даем завершиться параллельным чанкам пакета
                    print(f"\n[✔] Рендеринг завершен! Перехвачено {len(new_net_images)} изображений из потока...", flush=True)
                    for idx, (img_url, raw) in enumerate(new_net_images[:count]):
                        ext = ".png"
                        if raw[:4] == b"RIFF" and b"WEBP" in raw[:12]:
                            ext = ".webp"
                        elif raw[:3] == b"\xff\xd8\xff":
                            ext = ".jpg"
                        timestamp = int(time.time())
                        fn = out_dir / f"image_{timestamp}_{idx+1}{ext}"
                        fn.write_bytes(raw)
                        saved_files.append(fn)
                        print(f"    [✔] Сохранено: {fn.name} ({len(raw)} байт)", flush=True)
                    break

                # Способ 2: Захват из DOM (Canvas / Fetch fallback)
                new_items = await page.evaluate("""async (initialList) => {
                    const initialSet = new Set(initialList);
                    const imgs = Array.from(document.querySelectorAll('img'))
                        .filter(i => i.complete && i.naturalWidth > 200 && i.src && 
                                     (i.src.includes('flow-content.google') || i.src.includes('/asb/')) && 
                                     !initialSet.has(i.src));
                    
                    const results = [];
                    for (const img of imgs) {
                        let dataUrl = null;
                        // 1. Попытка экспорта через Canvas (несжатый PNG в полном разрешении)
                        try {
                            const canvas = document.createElement('canvas');
                            canvas.width = img.naturalWidth;
                            canvas.height = img.naturalHeight;
                            const ctx = canvas.getContext('2d');
                            ctx.drawImage(img, 0, 0);
                            dataUrl = canvas.toDataURL('image/png');
                        } catch (e) {}

                        // 2. Fallback: нативный fetch из контекста страницы
                        if (!dataUrl) {
                            try {
                                const resp = await fetch(img.src, { credentials: 'include' });
                                if (resp.ok) {
                                    const blob = await resp.blob();
                                    const reader = new FileReader();
                                    dataUrl = await new Promise((resolve) => {
                                        reader.onloadend = () => resolve(reader.result);
                                        reader.readAsDataURL(blob);
                                    });
                                }
                            } catch (e) {}
                        }

                        if (dataUrl) {
                            results.push({
                                src: img.src,
                                width: img.naturalWidth,
                                height: img.naturalHeight,
                                dataUrl: dataUrl
                            });
                        }
                    }
                    return results;
                }""", list(initial_set))

                if new_items:
                    print(f"\n[✔] Рендеринг завершен! Экспорт {len(new_items)} сгенерированных изображений из DOM...", flush=True)
                    for idx, item in enumerate(new_items[:count]):
                        try:
                            raw = base64.b64decode(item["dataUrl"].split(",", 1)[1])
                            timestamp = int(time.time())
                            ext = ".png"
                            if raw[:4] == b"RIFF" and b"WEBP" in raw[:12]:
                                ext = ".webp"
                            elif raw[:3] == b"\xff\xd8\xff":
                                ext = ".jpg"

                            fn = out_dir / f"image_{timestamp}_{idx+1}{ext}"
                            fn.write_bytes(raw)
                            saved_files.append(fn)
                            print(f"    [✔] Сохранено: {fn.name} ({len(raw)} байт, {item['width']}x{item['height']})", flush=True)
                        except Exception as e:
                            print(f"    [!] Ошибка экспорта изображения {idx+1}: {e}", flush=True)
                    break

            if not saved_files:
                print("\n[!] Изображение не появилось в ответе за отведенное время.", flush=True)

        finally:
            await context.close()

    return saved_files

async def generate_video_auto(
    prompt: str,
    out_dir: Path,
    model: str = "omni-flash",
    aspect: str = "16:9",
    duration: Optional[int] = None,
    profile: Optional[str] = None,
    exclude: Optional[set[str]] = None,
) -> Optional[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    profile_path, profile_display_name, profile_folder = get_automation_profile(profile, exclude=exclude)

    print(f"\n[+] Автоматическая генерация видео через Google Flow (Omni / Veo)...", flush=True)
    print(f"    Промпт : {prompt}", flush=True)
    print(f"    Профиль: {profile_display_name}", flush=True)
    print(f"    Папка  : {out_dir}\n", flush=True)

    out_file: Optional[Path] = None
    quota_state = {"exhausted": False, "reason": ""}
    captured_videos: list[tuple[str, bytes]] = []

    async with async_playwright() as pw:
        context, page = await get_browser_context(pw, profile_path, profile_folder)

        async def on_response(resp):
            if resp.status == 429:
                quota_state["exhausted"] = True
                quota_state["reason"] = f"HTTP 429 Too Many Requests (Превышен лимит запросов Flow)"
            elif resp.status == 200 and "flow-content.google/video" in resp.url:
                try:
                    body = await resp.body()
                    if len(body) > 100000:
                        captured_videos.append((resp.url, body))
                except Exception:
                    pass

        page.on("response", on_response)

        try:
            await ensure_flow_workspace(page)

            # Проверка лимитов на загруженной странице
            quota_err = await check_ui_quota_limits(page)
            if quota_err or quota_state["exhausted"]:
                reason = quota_err or quota_state["reason"]
                chrome_profiles.mark_profile_exhausted(profile_folder, reason)
                raise chrome_profiles.QuotaExceededError(profile_folder, reason)

            composer = page.locator("div.ProseMirror, [contenteditable='true'], [role='textbox']").first
            try:
                await composer.wait_for(state="visible", timeout=15000)
            except Exception:
                await asyncio.sleep(2)
                composer = page.locator("div.ProseMirror, [contenteditable='true'], [role='textbox']").first

            # Запоминаем текущие видео-карточки до отправки запроса
            initial_video_count = await page.locator("div.video-container, [aria-label*='Open video']").count()
            captured_videos.clear()

            print(f"    [Flow] Ввод промпта для видео...", flush=True)
            await composer.click()
            await asyncio.sleep(0.3)
            
            # Для режима Agent формулируем понятную инструкцию на генерацию видео
            if any(k in prompt.lower() for k in ["video", "видео", "клип"]):
                video_prompt = prompt
            else:
                video_prompt = f"Create a video of {prompt}"

            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await page.keyboard.type(video_prompt)
            await asyncio.sleep(0.8)

            submit_btn = page.locator(
                "button.generate-icon-button, button[aria-label*='Start generation'], "
                "button[aria-label*='Почати створення'], button[aria-label*='Start creating'], "
                "button[aria-label*='Generate'], button[aria-label*='Створити'], "
                "button:has-text('arrow_forward'), button[type='submit']"
            ).first

            captured_videos.clear()

            if await submit_btn.count():
                classes = await submit_btn.get_attribute("class") or ""
                disabled = await submit_btn.get_attribute("disabled")
                if "mat-button-disabled" in classes or disabled is not None:
                    print("    [Flow] Отправка запроса по клавише Enter...", flush=True)
                    await page.keyboard.press("Enter")
                else:
                    print("    [Flow] Отправка запроса...", flush=True)
                    await submit_btn.click()
            else:
                print("    [Flow] Отправка запроса по клавише Enter...", flush=True)
                await page.keyboard.press("Enter")

            print("[+] Запрос принят Google Flow! Ожидание генерации клипа (Gemini Omni / Veo)...", flush=True)

            for i in range(35):
                await asyncio.sleep(4)
                elapsed = (i + 1) * 4
                print(f"    ⏳ Рендеринг видео клипа... ({elapsed}с)", flush=True)

                if quota_state["exhausted"]:
                    chrome_profiles.mark_profile_exhausted(profile_folder, quota_state["reason"])
                    raise chrome_profiles.QuotaExceededError(profile_folder, quota_state["reason"])
                quota_err = await check_ui_quota_limits(page)
                if quota_err:
                    chrome_profiles.mark_profile_exhausted(profile_folder, quota_err)
                    raise chrome_profiles.QuotaExceededError(profile_folder, quota_err)

                # Способ 1: Прямой перехват видео-потока
                if captured_videos:
                    print("\n[✔] Видео перехвачено из сетевого потока Google Flow!", flush=True)
                    timestamp = int(time.time())
                    target_mp4 = out_dir / f"video_{timestamp}.mp4"
                    target_mp4.write_bytes(captured_videos[0][1])
                    print(f"[✔] Видео успешно сохранено: {target_mp4.name} ({len(captured_videos[0][1])} байт)", flush=True)
                    out_file = target_mp4
                    break

                # Способ 2: Скачивание через плеер карточки видео
                curr_video_count = await page.locator("div.video-container, [aria-label*='Open video']").count()
                if curr_video_count > initial_video_count or curr_video_count > 0:
                    video_card = page.locator("div.video-container, [aria-label*='Open video']").first
                    if await video_card.count():
                        try:
                            # Проверяем, не в процессе ли еще рендеринга карточка
                            badge = video_card.locator(".play-icon-badge, mat-icon:has-text('play_circle')")
                            if await badge.count():
                                print("\n[✔] Рендеринг видео завершен на доске! Открытие для экспорта...", flush=True)
                                await video_card.click()
                                await asyncio.sleep(2)
                                
                                dl_btn = page.locator("button[aria-label='Download media'], button[aria-label='Download']").first
                                if await dl_btn.count():
                                    await dl_btn.click()
                                    await asyncio.sleep(1)
                                    menu_opt = page.locator("[role='menuitem']:has-text('720p'), [role='menuitem']:has-text('Original'), button:has-text('720p')").first
                                    if await menu_opt.count():
                                        timestamp = int(time.time())
                                        target_mp4 = out_dir / f"video_{timestamp}.mp4"
                                        async with page.expect_download(timeout=45000) as dl_info:
                                            await menu_opt.click()
                                        dl = await dl_info.value
                                        await dl.save_as(str(target_mp4))
                                        print(f"[✔] Видео успешно скачано: {target_mp4.name} ({target_mp4.stat().st_size} байт)", flush=True)
                                        out_file = target_mp4
                                        break
                        except Exception as dl_ex:
                            # Если еще загружается, продолжаем ждать в цикле
                            pass

            if not out_file:
                print("\n[!] Видео не было готово за отведенное время.", flush=True)

        finally:
            await context.close()

    return out_file
