"""
Скрипт авторизации и управления профилями Google Flow.
Благодаря Zero-Login Sync система автоматически видит все профили Chrome (40+ аккаунтов).
Повторный вход не требуется, если в Google Chrome уже выполнен вход!
"""
import sys
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
VENV_GFLOW = BASE_DIR / ".venv" / "Scripts" / "gflow.exe"

def get_gflow_bin() -> str:
    if VENV_GFLOW.exists():
        return str(VENV_GFLOW)
    return "gflow"

def main():
    parser = argparse.ArgumentParser(description="Google Flow: Проверка сессий и авторизация")
    parser.add_argument("--profile", type=str, default=None, help="Имя или номер профиля Chrome")
    parser.add_argument("--new", action="store_true", help="Открыть браузер для входа в новый аккаунт с нуля")
    args = parser.parse_args()

    profiles = chrome_profiles.get_all_chrome_profiles()
    active_profiles = [p for p in profiles if p["has_cookies"]]

    print("=" * 80)
    print(" 🚀 GOOGLE FLOW: ПРОВЕРКА АККАУНТОВ И АВТОРИЗАЦИИ")
    print("=" * 80)

    if active_profiles and not args.new:
        print(f"\n[✔] Обнаружено {len(profiles)} профилей Google Chrome ({len(active_profiles)} с активной сессией)!")
        print("Вам НЕ НУЖНО логиниться заново — генератор использует готовые аккаунты из Chrome.\n")

        print(f"{'#':<3} | {'Папка':<12} | {'Имя в Chrome':<22} | {'Google Email':<24} | {'Готов к Flow'}")
        print("-" * 80)
        for idx, p in enumerate(profiles, start=1):
            folder = p["folder"]
            name = p["name"]
            if len(name) > 20:
                name = name[:19] + "…"
            email = chrome_profiles.mask_email(p["email"]) or "(локальный)"
            status = "✔ ГОТОВ" if p["has_cookies"] else "⚠ НЕТ КУКОВ"
            print(f"{idx:<3} | {folder:<12} | {name:<22} | {email:<24} | {status}")
        print("-" * 80)

        # Если запросили синхронизировать конкретный профиль
        target_profile = chrome_profiles.resolve_profile_folder(args.profile)
        print(f"\n[+] Синхронизация сессии для профиля: {target_profile}...")
        synced_path = chrome_profiles.sync_chrome_profile_for_automation(target_profile, force_sync=True)
        print(f"[✔] Профиль '{target_profile}' успешно подготовлен в: {synced_path}")

        print("\n💡 Теперь можно генерировать видео и фото:")
        print('  .\\generate.bat "A futuristic city in neon rain" --profile 2')
        print('  .\\generate.bat "A cybernetic dragon" --profile auto  (ротация по 40 аккаунтам)')
        print('  .\\generate_image.bat "A cute neon red panda" --profile 3')
        print("  .\\start_server.bat  (запуск REST API и Swagger UI)\n")
        return

    # Если профилей нет или запрошен вход в абсолютно новый аккаунт (--new)
    print("\n[i] Запуск браузера для ручного входа в новый аккаунт...")
    cmd = [get_gflow_bin(), "auth", "login", "--browser", "chrome"]
    if args.profile:
        cmd.extend(["--profile", args.profile])

    result = subprocess.run(cmd)
    if result.returncode == 0:
        print("\n[✔] Авторизация успешно сохранена!")
    else:
        print(f"\n[-] Процесс завершился с кодом {result.returncode}.")

if __name__ == "__main__":
    main()
