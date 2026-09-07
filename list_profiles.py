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
    print(f"{'#':<3} | {'Папка':<12} | {'Имя в Chrome':<20} | {'Google Email':<22} | {'Статус'}")
    print("-" * 80)

    import time
    for idx, p in enumerate(profiles, start=1):
        folder = p["folder"]
        name = p["name"]
        if len(name) > 18:
            name = name[:17] + "…"
        email = chrome_profiles.mask_email(p["email"]) or "(локальный)"
        if len(email) > 20:
            email = email[:19] + "…"
        is_verified, _ = chrome_profiles.verify_session(folder)
        if p.get("is_exhausted"):
            until_ts = p.get("cooldown_until", 0)
            t_str = time.strftime('%H:%M', time.localtime(until_ts)) if until_ts else ""
            status = f"⏳ ЛИМИТ (до {t_str})"
        elif is_verified:
            status = "✔ FLOW СЕССИЯ"
        elif p["has_cookies"]:
            status = "✔ ГОТОВ К ВХОДУ"
        else:
            status = "⚠ НЕТ КУКОВ"
        print(f"{idx:<3} | {folder:<12} | {name:<20} | {email:<22} | {status}")

    print("-" * 80)
    print("\n💡 Как использовать профили для генерации:")
    print('  1. Авто-ротация:       .\\generate.bat "Промпт" --profile auto   (переключает при исчерпании лимитов)')
    print('  2. По номеру:          .\\generate.bat "Промпт" --profile 2')
    print('  3. По имени папки:     .\\generate.bat "Промпт" --profile "Profile 2"')
    print('  4. По имени в Chrome:  .\\generate.bat "Промпт" --profile "GeminiPro"')
    print('  5. Сброс лимитов:      .\\generate.bat --reset-limits')
    print('  6. Для фото:           .\\generate_image.bat "Промпт" --profile auto\n')

if __name__ == "__main__":
    main()
