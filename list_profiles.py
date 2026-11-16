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

    profiles = gflow_backend.get_unified_profiles()
    if not profiles:
        print(" [i] Профили Chrome или gflow не найдены.")
        print("\n💡 Как авторизовать аккаунты точечно:")
        print("    .\\login.bat 1    (войти в аккаунт #1)")
        print("    .\\login.bat 10   (войти в аккаунт #10)")
        print("    .\\login.bat 34   (войти в аккаунт #34)")
        print("\n💡 Или просто запустите: .\\login.bat")
        print("=" * 80)
        return

    print(f"Всего обнаружено профилей: {len(profiles)}\n")
    print(f"{'#':<4} | {'ID профиля':<12} | {'Имя в Chrome':<20} | {'Google Email':<26} | {'Статус Flow'}")
    print("-" * 80)

    for p in profiles:
        idx = p["num"]
        pid = p["id"]
        cname = p["name"]
        if len(cname) > 18:
            cname = cname[:17] + "…"
        email = p.get("email", "") or "(локальный)"
        if len(email) > 24:
            email = email[:23] + "…"
        status = p["status"]
        print(f"{idx:<4} | {pid:<12} | {cname:<20} | {email:<26} | {status}")

    print("-" * 80)
    print("\n💡 Как использовать профили для генерации:")
    print('  1. Авто-ротация по всем: .\\generate.bat "Промпт" --profile auto')
    print('  2. Точечно в аккаунт 2:  .\\generate.bat 2 "Промпт"')
    print('  3. Для генерации фото:   .\\generate_image.bat 2 "Промпт"')
    print('  4. Сброс лимитов/квот:   .\\generate.bat --reset-limits')
    print('  5. Авторизация аккаунта: .\\login.bat 2 (или любой номер 1..34)\n')

if __name__ == "__main__":
    main()

