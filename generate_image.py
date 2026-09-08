"""
CLI утилита для генерации изображений через Google Flow (Imagen 4 / Nano Banana)
"""
import sys
import os
import subprocess
import argparse
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).parent.resolve()
VENV_GFLOW = BASE_DIR / ".venv" / "Scripts" / "gflow.exe"
OUTPUT_DIR = BASE_DIR / "output" / "images"

def get_gflow_bin() -> str:
    if VENV_GFLOW.exists():
        return str(VENV_GFLOW)
    return "gflow"

def check_auth() -> bool:
    cmd = [get_gflow_bin(), "auth", "status"]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.returncode == 0

import chrome_profiles

def generate_image(
    prompt: str,
    model: str = "nano-pro",
    aspect: str = "16:9",
    count: int = 1,
    out_dir: Path | None = None,
    profile: str | None = None,
):
    out_dir = out_dir or OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    profile = profile or "auto"

    # Режим автоматической ротации при исчерпании лимитов
    if profile.lower() in ("auto", "rotate", "next"):
        all_profiles = chrome_profiles.get_all_chrome_profiles()
        max_attempts = max(len(all_profiles), 1)
        attempted_profiles: set[str] = set()

        print(f"\n[Auto-Rotation] Режим автоматической ротации аккаунтов (всего обнаружено {len(all_profiles)} профилей).")
        for attempt in range(max_attempts):
            candidate = chrome_profiles.resolve_profile_folder("auto", exclude=attempted_profiles)
            if candidate in attempted_profiles:
                print("\n[!] Все доступные профили Chrome исчерпали квоту генераций!")
                exhausted = chrome_profiles.get_exhausted_profiles()
                if exhausted:
                    print("    Статус исчерпанных профилей:")
                    import time
                    for f, info in exhausted.items():
                        cooldown_ts = info.get("cooldown_until", 0)
                        print(f"    - {f}: {info.get('reason')} (до {time.strftime('%H:%M:%S', time.localtime(cooldown_ts))})")
                print("    Для сброса таймеров выполните: .\\generate_image.bat --reset-limits\n")
                sys.exit(1)

            print(f"\n[Auto-Rotation] 🚀 Попытка генерации через аккаунт '{candidate}' ({attempt + 1}/{max_attempts})...")
            try:
                import asyncio
                from flow_engine import generate_image_auto
                res_files = asyncio.run(
                    generate_image_auto(
                        prompt=prompt,
                        out_dir=out_dir,
                        model=model,
                        aspect=aspect,
                        count=count,
                        profile=candidate,
                    )
                )
                if res_files:
                    print(f"\n[✔] Изображения успешно сохранены ({len(res_files)} шт.) в: {out_dir}")
                    return
            except chrome_profiles.QuotaExceededError as qe:
                print(f"\n[Auto-Rotation] ⚠️ На профиле '{qe.profile}' закончились кредиты/квота: {qe.reason}")
                chrome_profiles.mark_profile_exhausted(qe.profile, qe.reason)
                attempted_profiles.add(qe.profile)
                print(f"[Auto-Rotation] 🔄 Автоматический переход на следующий аккаунт из пула...")
                continue
            except Exception as exc:
                print(f"[-] Ошибка генерации на профиле '{candidate}': {exc}")
                attempted_profiles.add(candidate)
                continue

        print("\n[-] Не удалось завершить генерацию изображений ни на одном из доступных аккаунтов.")
        sys.exit(1)
    else:
        try:
            import asyncio
            from flow_engine import generate_image_auto
            res_files = asyncio.run(
                generate_image_auto(
                    prompt=prompt,
                    out_dir=out_dir,
                    model=model,
                    aspect=aspect,
                    count=count,
                    profile=profile,
                )
            )
            if res_files:
                print(f"\n[✔] Изображения успешно сохранены ({len(res_files)} шт.) в: {out_dir}")
                return
        except chrome_profiles.QuotaExceededError as qe:
            print(f"\n[-] Лимит генераций исчерпан для профиля '{qe.profile}': {qe.reason}")
            print("💡 СОВЕТ: Запустите генерацию с флагом --profile auto для автоматического переключения на следующий аккаунт!")
            print(f'   Пример: .\\generate_image.bat "{prompt}" --profile auto\n')
            sys.exit(1)
        except Exception as exc:
            print(f"[-] Ошибка генерации: {exc}")
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Google Flow (Imagen / Nano Banana) Image Generator")
    parser.add_argument("prompt", type=str, nargs="?", default=None, help="Текстовый промпт для генерации изображения")
    parser.add_argument(
        "--model",
        type=str,
        default="nano-pro",
        choices=["nano2", "nano-pro", "image4", "imagen4"],
        help="Модель генерации (nano-pro - высокое качество, image4 - Imagen 4, nano2 - быстрый)",
    )
    parser.add_argument(
        "--aspect",
        type=str,
        default="16:9",
        choices=["16:9", "9:16", "1:1", "4:3", "3:4"],
        help="Соотношение сторон (16:9, 9:16, 1:1, 4:3, 3:4)",
    )
    parser.add_argument(
        "-n", "--count",
        type=int,
        default=1,
        choices=[1, 2, 3, 4],
        help="Количество вариантов (1-4)",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=None,
        help="Папка для сохранения (по умолчанию ./output/images)",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Профиль Chrome (например: 2, 'Profile 2', 'GeminiPro' или 'auto' для ротации 40 аккаунтов)",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="Показать список всех доступных профилей Chrome и выйти",
    )
    parser.add_argument(
        "--reset-limits",
        action="store_true",
        help="Сбросить статус исчерпанных лимитов/квот для всех профилей и выйти",
    )

    args = parser.parse_args()

    if args.reset_limits:
        chrome_profiles.reset_exhausted_limits()
        print("\n[✔] Кэш исчерпанных лимитов успешно сброшен. Все профили снова активны!\n")
        return

    if args.list_profiles:
        import list_profiles
        list_profiles.main()
        return

    if not args.prompt:
        try:
            print("\n" + "=" * 65)
            print(" 🎨 GOOGLE FLOW STUDIO — ГЕНЕРАТОР ИЗОБРАЖЕНИЙ (IMAGEN 4)")
            print("=" * 65)
            print(" Режим: Автоматическая ротация по всем профилям Chrome")
            print(" Подсказка: Вы также можете передавать параметры в консоли:")
            print('   .\\generate_image.bat "Ваш промпт" --profile auto')
            print("=" * 65)
            user_input = input("\n[?] Введите текстовый промпт для генерации: ").strip()
            if not user_input:
                print("\n[!] Ошибка: Промпт не может быть пустым.")
                sys.exit(1)
            args.prompt = user_input
        except (KeyboardInterrupt, EOFError):
            print("\nОперация отменена.")
            sys.exit(0)

    out_dir = Path(args.out_dir) if args.out_dir else None

    generate_image(
        prompt=args.prompt,
        model=args.model,
        aspect=args.aspect,
        count=args.count,
        out_dir=out_dir,
        profile=args.profile,
    )

if __name__ == "__main__":
    main()
