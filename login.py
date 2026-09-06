"""
Скрипт для разовой авторизации в Google Flow через Chrome.
Сессия сохраняется локально и в дальнейшем используется автоматически для CLI и Web API.
"""
import sys
import argparse
import subprocess
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).parent.resolve()
VENV_GFLOW = BASE_DIR / ".venv" / "Scripts" / "gflow.exe"

def get_gflow_bin() -> str:
    if VENV_GFLOW.exists():
        return str(VENV_GFLOW)
    return "gflow"

def main():
    parser = argparse.ArgumentParser(description="Google Flow: Авторизация")
    parser.add_argument("--profile", type=str, default=None, help="Имя профиля Flow (опционально)")
    args = parser.parse_args()

    cmd = [get_gflow_bin(), "auth", "login", "--browser", "chrome"]
    if args.profile:
        cmd.extend(["--profile", args.profile])

    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\n[✔] Авторизация успешно сохранена!")
        print("Теперь можно отдавать промпты:")
        print('  .\\generate.bat "A futuristic flying car"')
        print("или запустить Web API:")
        print("  .\\start_server.bat\n")
    else:
        print(f"\n[-] Завершено с кодом {result.returncode}.")

if __name__ == "__main__":
    main()
