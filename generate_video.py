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
        print(f"\n[-] Ошибка генерации (код {ret}).")
        if not check_auth():
            print("\n[!] Похоже, сессия не авторизована или истекла.")
            print("    Выполните вход: python login.py или .\\login.bat\n")
        sys.exit(ret)
    else:
        print(f"\n[✔] Видео успешно сгенерировано в: {out_dir}")

def main():
    parser = argparse.ArgumentParser(description="Google Flow (Veo / Gemini Omni) Video Generator")
    parser.add_argument("prompt", type=str, help="Текстовый промпт для генерации видео")
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
        help="Папка для сохранения видео (по умолчанию ./output)",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Имя профиля Flow (если используется несколько аккаунтов)",
    )

    args = parser.parse_args()
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
