"""
Утилита для просмотра и проверки профилей Google Flow (1..34+ аккаунтов).
Показывает статус каждого профиля (авторизован / исчерпан лимит / требует входа).
"""
import sys
import time
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))
import gflow_backend

def main():
    print("=" * 80)
    print(" 🚀 GOOGLE FLOW: СПИСОК АККАУНТОВ И СТАТУС СЕССИЙ")
    print("=" * 80)

    profiles = gflow_backend.list_profiles()
    if not profiles:
        print(" [i] В базе пока нет авторизованных профилей gflow.")
        print("\n💡 Как авторизовать аккаунты точечно:")
        print("    .\\login.bat 1    (войти в аккаунт #1)")
        print("    .\\login.bat 10   (войти в аккаунт #10)")
        print("    .\\login.bat 34   (войти в аккаунт #34)")
        print("\n💡 Или просто запустите: .\\login.bat")
        print("=" * 80)
        return

    print(f"Всего обнаружено профилей в gflow: {len(profiles)}\n")
    print(f"{'#':<4} | {'Профиль':<12} | {'Google Email':<28} | {'Статус сессии'}")
    print("-" * 80)

    for idx, p in enumerate(profiles, start=1):
        name = p["name"]
        email = p.get("email", "") or "(вход выполнен)"
        if len(email) > 26:
            email = email[:25] + "…"
        
        if p.get("is_exhausted"):
            until_ts = p.get("cooldown_until", 0)
            t_str = time.strftime('%H:%M', time.localtime(until_ts)) if until_ts else ""
            status = f"⏳ ЛИМИТ ДО {t_str}"
        elif p.get("has_cookies"):
            status = "✔ ГОТОВ К ГЕНЕРАЦИИ"
        else:
            status = "⚠ ТРЕБУЕТ ВХОДА"
        print(f"{idx:<4} | {name:<12} | {email:<28} | {status}")

    print("-" * 80)
    print("\n💡 Как использовать профили для генерации:")
    print('  1. Авто-ротация по всем: .\\generate.bat "Промпт" --profile auto')
    print('  2. Точечно в аккаунт 10: .\\generate.bat 10 "Промпт"')
    print('  3. Для генерации фото:   .\\generate_image.bat 10 "Промпт"')
    print('  4. Сброс лимитов/квот:   .\\generate.bat --reset-limits')
    print('  5. Авторизация аккаунта: .\\login.bat 10\n')

if __name__ == "__main__":
    main()

