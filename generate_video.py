"""
CLI утилита для генерации видео через Google Flow (Veo / Gemini Omni)
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
OUTPUT_DIR = BASE_DIR / "output"

def get_gflow_bin() -> str:
    if VENV_GFLOW.exists():
        return str(VENV_GFLOW)
    return "gflow"

def check_auth() -> bool:
    cmd = [get_gflow_bin(), "auth", "status"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0

import chrome_profiles

def generate_video(
    prompt: str,
    model: str = "omni-flash",
    aspect: str = "16:9",
    duration: int | None = None,
    out_dir: Path | None = None,
    profile: str | None = None,
):
    out_dir = out_dir or OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # Режим автоматической ротации при исчерпании лимитов
    if profile and profile.lower() in ("auto", "rotate", "next"):
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
                print("    Для сброса таймеров выполните: .\\generate.bat --reset-limits\n")
                sys.exit(1)

            print(f"\n[Auto-Rotation] 🚀 Попытка генерации через аккаунт '{candidate}' ({attempt + 1}/{max_attempts})...")
            try:
                import asyncio
                from flow_engine import generate_video_auto
                res_file = asyncio.run(
                    generate_video_auto(
                        prompt=prompt,
                        out_dir=out_dir,
                        model=model,
                        aspect=aspect,
                        duration=duration,
                        profile=candidate,
                    )
                )
                if res_file and res_file.exists():
                    print(f"\n[✔] Видео успешно сгенерировано и сохранено: {res_file}")
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

        print("\n[-] Не удалось завершить генерацию видео ни на одном из доступных аккаунтов.")
        sys.exit(1)

    cmd = [
        get_gflow_bin(),
        "video",
        "t2v",
        prompt,
        "--model", model,
        "--aspect", aspect,
        "--out-dir", str(out_dir),
    ]

    if duration:
        cmd.extend(["--duration", str(duration)])
    if profile:
        cmd.extend(["--profile", profile] )

    print(f"\n[+] Запуск генерации видео...")
    print(f"    Промпт : {prompt}")
    print(f"    Модель : {model}")
    print(f"    Формат : {aspect}")
    if duration:
        print(f"    Длительность: {duration}с")
    print(f"    Папка  : {out_dir}\n")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    output_lines = []
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        if line:
            print(line, end="")
            output_lines.append(line)

    ret = process.poll()
    if ret != 0:
        print(f"\n[*] Переключение на прямой режим автоматизации Google Flow...")
        try:
            import asyncio
            from flow_engine import generate_video_auto
            res_file = asyncio.run(
                generate_video_auto(
                    prompt=prompt,
                    out_dir=out_dir,
                    model=model,
                    aspect=aspect,
                    duration=duration,
                    profile=profile,
                )
            )
            if res_file and res_file.exists():
                print(f"\n[✔] Видео успешно сгенерировано и сохранено: {res_file}")
                return
        except chrome_profiles.QuotaExceededError as qe:
            print(f"\n[-] Лимит генераций исчерпан для профиля '{qe.profile}': {qe.reason}")
            print("💡 СОВЕТ: Запустите генерацию с флагом --profile auto для автоматического переключения на следующий аккаунт!")
            print(f'   Пример: .\\generate.bat "{prompt}" --profile auto\n')
            sys.exit(1)
        except Exception as exc:
            print(f"[-] Ошибка прямого режима: {exc}")

        print(f"\n[-] Ошибка генерации (код {ret}).")
        if not check_auth():
            print("\n[!] Похоже, сессия не авторизована или истекла.")
            print("    Выполните вход: python login.py или .\\login.bat\n")
        sys.exit(ret)
    else:
        print(f"\n[✔] Видео успешно сгенерировано в: {out_dir}")

def main():
    parser = argparse.ArgumentParser(description="Google Flow (Veo / Gemini Omni) Video Generator")
    parser.add_argument("prompt", type=str, nargs="?", default=None, help="Текстовый промпт для генерации видео")
    parser.add_argument(
        "--model",
        type=str,
        default="omni-flash",
        choices=["omni-flash", "veo-quality", "veo-fast", "veo-lite", "veo-lite-lp"],
        help="Модель генерации видео (по умолчанию omni-flash / Gemini Omni)",
    )
    parser.add_argument(
        "--aspect",
        type=str,
        default="16:9",
        choices=["16:9", "9:16"],
        help="Соотношение сторон (16:9 или 9:16)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        choices=[4, 6, 8, 10],
        help="Длительность клипа (omni-flash поддерживает 4, 6, 8, 10; Veo 3.1: 4, 6, 8)",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=None,
        help="Папка для сохранения видео (по умолчанию ./output/videos)",
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
        parser.print_help()
        print("\n[!] Ошибка: Укажите текстовый промпт в кавычках.")
        print('    Пример: .\\generate.bat "A cute robot waving hello" --profile auto')
        sys.exit(1)

    out_dir = Path(args.out_dir) if args.out_dir else None

    generate_video(
        prompt=args.prompt,
        model=args.model,
        aspect=args.aspect,
        duration=args.duration,
        out_dir=out_dir,
        profile=args.profile,
    )

if __name__ == "__main__":
    main()
