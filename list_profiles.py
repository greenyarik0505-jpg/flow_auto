"""
Утилита для просмотра и проверки профилей Google Chrome.
Позволяет увидеть все доступные аккаунты для Google Flow (40+ профилей)
и узнать, как запускать генерацию с конкретного аккаунта.
"""
import sys
from pathlib import Path
import chrome_profiles

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def main():
    print("=" * 80)
    print(" 🚀 GOOGLE FLOW: ПРОФИЛИ GOOGLE CHROME (ZERO-LOGIN)")
    print("=" * 80)

    user_data_path = chrome_profiles.get_chrome_user_data_path()
    print(f"Каталог данных Chrome: {user_data_path}\n")

    profiles = chrome_profiles.get_all_chrome_profiles(user_data_path)
    if not profiles:
        print("[-] Профили Google Chrome не найдены.")
        print("Убедитесь, что Google Chrome установлен, или укажите путь через переменную CHROME_USER_DATA.")
        return

    print(f"Обнаружено профилей: {len(profiles)}\n")
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
    print("\n💡 Как использовать профили для генерации:")
    print('  1. По номеру:          .\\generate.bat "Промпт" --profile 2')
    print('  2. По имени папки:     .\\generate.bat "Промпт" --profile "Profile 2"')
    print('  3. По имени в Chrome:  .\\generate.bat "Промпт" --profile "GeminiPro"')
    print('  4. Авто-ротация:       .\\generate.bat "Промпт" --profile auto   (переключает 40 аккаунтов по кругу)')
    print('  5. Для фото:           .\\generate_image.bat "Промпт" --profile 2\n')

if __name__ == "__main__":
    main()
