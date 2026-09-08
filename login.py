"""
Скрипт авторизации и управления аккаунтами Google Flow (1..34+ профилей).
Работает на базе официального gflow CLI с изолированными persistent-профилями Chrome.
Позволяет точечно авторизовать любой аккаунт (например, 10) без затрагивания остальных.
"""
import sys
import os
import re
import argparse
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

def parse_profile_range(input_str: str) -> list[str]:
    """Разбирает строку вида '10', '1-5', '1,2,10' в список имен профилей."""
    s = input_str.strip()
    if not s:
        return []
    if s.lower() in ("all", "все", "a"):
        return ["all"]
    
    # Диапазон вида 1-5
    range_match = re.match(r"^(\d+)\s*-\s*(\d+)$", s)
    if range_match:
        start_idx = int(range_match.group(1))
        end_idx = int(range_match.group(2))
        if start_idx <= end_idx:
            return [str(i) for i in range(start_idx, end_idx + 1)]
        else:
            return [str(i) for i in range(start_idx, end_idx - 1, -1)]

    # Список через запятую или пробел: 1, 2, 10
    items = re.split(r"[,;\s]+", s)
    result = []
    for item in items:
        clean = gflow_backend.normalize_profile_name(item)
        if clean and clean != "auto":
            result.append(clean)
    return result

def show_profiles_table(profiles: list[dict]) -> None:
    """Выводит красивую таблицу текущего состояния профилей gflow."""
    print("=" * 80)
    print(" 🚀 GOOGLE FLOW: СТАТУС СЕССИЙ АККАУНТОВ (GFLOW CLI)")
    print("=" * 80)
    if not profiles:
        print(" [i] В базе пока нет авторизованных профилей.")
        print(" 💡 Вы можете точечно авторизовать любой аккаунт:")
        print("    .\\login.bat 1")
        print("    .\\login.bat 10")
        print("    .\\login.bat 34")
        print("=" * 80)
        return

    print(f"{'#':<4} | {'Профиль':<12} | {'Google Email':<28} | {'Статус'}")
    print("-" * 80)
    for idx, p in enumerate(profiles, start=1):
        name = p["name"]
        email = p.get("email", "") or "(вход выполнен)"
        if len(email) > 26:
            email = email[:25] + "…"
        if p.get("is_exhausted"):
            status = "⏳ ЛИМИТ (429)"
        elif p.get("has_cookies"):
            status = "✔ ГОТОВ К РАБОТЕ"
        else:
            status = "⚠ ТРЕБУЕТ ВХОДА"
        print(f"{idx:<4} | {name:<12} | {email:<28} | {status}")
    print("-" * 80)

def main():
    parser = argparse.ArgumentParser(description="Google Flow: Точечная авторизация аккаунтов (1..34+ профилей)")
    parser.add_argument("profile", type=str, nargs="?", default=None, help="Номер или имя профиля (например: 10, 'Profile 10', 1-5)")
    parser.add_argument("--profile", dest="profile_opt", type=str, default=None, help="Имя или номер профиля")
    parser.add_argument("--all", action="store_true", help="Последовательно авторизовать диапазон профилей")
    parser.add_argument("--list", action="store_true", help="Только показать статус всех сохраненных профилей")
    parser.add_argument("--reset-limits", action="store_true", help="Сбросить статус исчерпанных квот/лимитов")
    args = parser.parse_args()

    if args.reset_limits:
        gflow_backend.reset_limits()
        print("\n[✔] Кэш исчерпанных лимитов gflow успешно сброшен!\n")
        return

    profiles = gflow_backend.list_profiles()

    if args.list:
        show_profiles_table(profiles)
        return

    profile_selector = args.profile or args.profile_opt

    # 1. Интерактивный режим, если профиль не передан в командной строке
    if not profile_selector and not args.all:
        show_profiles_table(profiles)
        print("\n" + "=" * 80)
        print(" [?] ТОЧЕЧНЫЙ ВЫБОР АККАУНТА ДЛЯ ВХОДА:")
        print("     - Введите номер аккаунта (например: 10, 1, 2, 34)")
        print("     - Введите диапазон для входа по очереди (например: 1-5)")
        print("     - Введите 'all' для входа в профили 1..34 по очереди")
        print("     - Нажмите Enter для выхода")
        print("=" * 80)
        try:
            choice = input("\n👉 Номер аккаунта: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nВыход.")
            return

        if not choice:
            print("Выход.")
            return
        profile_selector = choice

    # 2. Обработка 'all'
    if args.all or (profile_selector and profile_selector.lower() in ("all", "все", "a")):
        print("\n" + "=" * 80)
        print(" ⚠️ ВНИМАНИЕ: Вы выбрали режим последовательной авторизации ВСЕХ аккаунтов.")
        print("=" * 80)
        try:
            count_str = input("👉 Сколько аккаунтов авторизовать? [по умолчанию 34]: ").strip()
            max_acc = int(count_str) if count_str.isdigit() else 34
        except (KeyboardInterrupt, EOFError):
            print("\nОтмена.")
            return

        print(f"\n[+] Будет запущена авторизация аккаунтов от 1 до {max_acc} по очереди.")
        print("💡 Вы в любой момент можете прервать процесс комбинацией Ctrl+C.\n")

        for num in range(1, max_acc + 1):
            prof_name = str(num)
            print(f"\n>>> ШАГ {num} ИЗ {max_acc}: Вход в аккаунт #{prof_name} <<<")
            success = gflow_backend.login(prof_name)
            if not success:
                print(f"[!] Авторизация профиля {prof_name} не была завершена.")
                try:
                    c = input("Продолжить со следующим аккаунтом? [Y/n]: ").strip().lower()
                    if c in ("n", "no", "нет"):
                        break
                except (KeyboardInterrupt, EOFError):
                    break
        print("\n[✔] Пакетная авторизация завершена.\n")
        return

    # 3. Разбор точечного ввода или диапазона (например: '10' или '1-3' или '1,2,10')
    targets = parse_profile_range(profile_selector)
    if not targets:
        print(f"[-] Не удалось определить имя или номер профиля: '{profile_selector}'")
        return

    if len(targets) == 1:
        target = targets[0]
        print("\n" + "=" * 80)
        print(f" 🎯 ТОЧЕЧНЫЙ ВХОД В АККАУНТ #{target}")
        print("=" * 80)
        print(f" Выбран ТОЛЬКО аккаунт #{target}. Другие профили НЕ затрагиваются.")
        print("=" * 80)
        gflow_backend.login(target)
    else:
        print(f"\n[+] Выбрана авторизация следующих {len(targets)} профилей: {', '.join(targets)}")
        for idx, target in enumerate(targets, start=1):
            print(f"\n>>> ШАГ {idx} ИЗ {len(targets)}: Аккаунт #{target} <<<")
            success = gflow_backend.login(target)
            if not success and idx < len(targets):
                try:
                    c = input("Продолжить со следующим? [Y/n]: ").strip().lower()
                    if c in ("n", "no", "нет"):
                        break
                except (KeyboardInterrupt, EOFError):
                    break
        print("\n[✔] Авторизация выбранных аккаунтов завершена.\n")

if __name__ == "__main__":
    main()

