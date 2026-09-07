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

    cmd = [
        get_gflow_bin(),
        "image",
        "t2i",
        prompt,
        "--model", model,
        "--aspect", aspect,
        "-n", str(count),
        "--out", str(out_dir),
    ]

    if profile:
        cmd.extend(["--profile", profile])

    print(f"\n[+] Запуск генерации изображения...")
    print(f"    Промпт     : {prompt}")
    print(f"    Модель     : {model}")
    print(f"    Формат     : {aspect}")
    print(f"    Количество : {count}")
    print(f"    Папка      : {out_dir}\n")

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
        except Exception as exc:
            print(f"[-] Ошибка прямого режима: {exc}")

        print(f"\n[-] Ошибка генерации изображения (код {ret}).")
        if not check_auth():
            print("\n[!] Похоже, сессия не авторизована или истекла.")
            print("    Выполните вход: .\\login.bat\n")
        sys.exit(ret)
    else:
        print(f"\n[✔] Изображение успешно сгенерировано в папке: {out_dir}")

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

    args = parser.parse_args()

    if args.list_profiles:
        import list_profiles
        list_profiles.main()
        return

    if not args.prompt:
        parser.print_help()
        print("\n[!] Ошибка: Укажите текстовый промпт в кавычках.")
        print('    Пример: .\\generate_image.bat "Futuristic car" --profile 2')
        sys.exit(1)

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
