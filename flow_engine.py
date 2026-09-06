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

def get_profile_path(profile_name: Optional[str] = None) -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    base = Path(local_app_data) / "ffroliva" / "gflow-cli"
    if profile_name:
        p = base / f"profile_{profile_name}"
        if p.exists():
            return p
        return base / profile_name

    profiles = list(base.glob("profile_*"))
    for p in profiles:
        if "default" not in p.name:
            return p
    if (base / "profile_default").exists():
        return base / "profile_default"
    return base / "profile_default"

async def generate_image_auto(
    prompt: str,
    out_dir: Path,
    model: str = "nano-pro",
    aspect: str = "16:9",
    count: int = 1,
    profile: Optional[str] = None,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    profile_path = get_profile_path(profile)
    
    print(f"\n[+] Автоматическая генерация фото через Google Flow...")
    print(f"    Промпт: {prompt}")
    print(f"    Профиль: {profile_path.name}")
    print(f"    Папка : {out_dir}\n")

    saved_files: list[Path] = []

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_path),
            channel="chrome",
            headless=True,
            args=["--password-store=basic", "--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else await context.new_page()

        await page.goto("https://flow.google.com/", wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(4)

        composer = page.locator("[contenteditable='true'].ProseMirror, [contenteditable='true']").first
        if not await composer.count():
            prj = page.locator("a[href*='/project/']").first
            if await prj.count():
                await prj.click()
                await asyncio.sleep(4)

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
    profile_path = get_profile_path(profile)

    print(f"\n[+] Автоматическая генерация видео через Google Flow (Omni / Veo)...")
    print(f"    Промпт: {prompt}")
    print(f"    Профиль: {profile_path.name}")
    print(f"    Папка : {out_dir}\n")

    out_file: Optional[Path] = None

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_path),
            channel="chrome",
            headless=True,
            args=["--password-store=basic", "--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else await context.new_page()

        await page.goto("https://flow.google.com/", wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(4)

        prj = page.locator("a[href*='/project/']").first
        if await prj.count():
            await prj.click()
            await asyncio.sleep(4)

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

        await context.close()

    return out_file
