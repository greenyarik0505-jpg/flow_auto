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
import re
import gflow_backend

def is_profile_like_arg(arg: str) -> bool:
    s = str(arg).strip()
    if not s:
        return False
    if s.isdigit():
        return True
    if re.match(r"^#\d+$", s):
        return True
    if re.match(r"^(?:profile\s*|p)\d+$", s, re.IGNORECASE):
        return True
    if s.lower() in ("default", "auto", "rotate", "next"):
        return True
    for p in gflow_backend.list_profiles():
        if p["name"].lower() == s.lower():
            return True
    return False

def generate_video(
    prompt: str,
    model: str = "omni-flash",
    aspect: str = "16:9",
    duration: int | None = None,
    out_dir: Path | None = None,
    profile: str | None = None,
):
    return gflow_backend.generate_video(
        prompt=prompt,
        model=model,
        aspect=aspect,
        duration=duration,
        out_dir=out_dir,
        profile=profile,
    )

def main():
    parser = argparse.ArgumentParser(description="Google Flow (Veo / Gemini Omni) Video Generator")
    parser.add_argument("prompt", type=str, nargs="*", default=None, help="Текстовый промпт для генерации видео")
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
        gflow_backend.reset_limits()
        chrome_profiles.reset_exhausted_limits()
        print("\n[✔] Кэш исчерпанных лимитов успешно сброшен. Все профили снова активны!\n")
        return

    if args.list_profiles:
        import list_profiles
        list_profiles.main()
        return

    prompt = None
    profile = args.profile

    if args.prompt:
        parts = args.prompt if isinstance(args.prompt, list) else [args.prompt]
        if len(parts) == 1:
            p0 = parts[0]
            if is_profile_like_arg(p0) and not profile:
                profile = p0
            else:
                prompt = p0
        elif len(parts) >= 2:
            p0, p1 = parts[0], parts[1]
            if is_profile_like_arg(p0) and not is_profile_like_arg(p1):
                profile = profile or p0
                prompt = " ".join(parts[1:])
            elif is_profile_like_arg(p1) and not is_profile_like_arg(p0):
                profile = profile or p1
                prompt = parts[0]
            else:
                if is_profile_like_arg(p1):
                    profile = profile or p1
                    prompt = parts[0]
                else:
                    prompt = " ".join(parts)

    if not prompt:
        try:
            print("\n" + "=" * 65)
            print(" 🎬 GOOGLE FLOW STUDIO — ГЕНЕРАТОР ВИДЕО (VEO / OMNI)")
            print("=" * 65)
            if profile:
                resolved_p = gflow_backend.normalize_profile_name(profile)
                print(f" Выбранный профиль: {resolved_p}")
            else:
                print(" Подсказка: Вы можете указать профиль: .\\generate.bat 10 \"Промпт\"")
            print("=" * 65)
            user_input = input("\n[?] Введите текстовый промпт для генерации видео: ").strip()
            if not user_input:
                print("\n[!] Ошибка: Промпт не может быть пустым.")
                sys.exit(1)
            prompt = user_input

            if not profile:
                print("\n[?] Выберите профиль для генерации:")
                print("    - Enter: 'auto' (автоматическая ротация по готовым аккаунтам)")
                print("    - Номер аккаунта (например: 1, 2, 10, 34)")
                print("    - Имя профиля (например: default)")
                prof_choice = input("👉 Профиль [по умолчанию auto]: ").strip()
                profile = prof_choice if prof_choice else "auto"
        except (KeyboardInterrupt, EOFError):
            print("\nОперация отменена.")
            sys.exit(0)

    profile = gflow_backend.normalize_profile_name(profile)

    out_dir = Path(args.out_dir) if args.out_dir else None

    generate_video(
        prompt=prompt,
        model=args.model,
        aspect=args.aspect,
        duration=args.duration,
        out_dir=out_dir,
        profile=profile,
    )

if __name__ == "__main__":
    main()
