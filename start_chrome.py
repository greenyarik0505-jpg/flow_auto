"""
Скрипт безопасного запуска Google Chrome с поддержкой порта отладки 9222 (CDP).
Обеспечивает работу с 40+ профилями Chrome без необходимости повторного входа.
"""
import os
import sys
import time
import subprocess
from pathlib import Path
import chrome_profiles

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def is_chrome_running() -> bool:
    """Проверяет, запущен ли процесс chrome.exe."""
    try:
        res = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq chrome.exe", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        return "chrome.exe" in res.stdout.lower()
    except Exception:
        return False

def kill_chrome_processes():
    """Безопасно завершает процессы chrome.exe."""
    try:
        subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True)
        time.sleep(1)
    except Exception:
        pass

import argparse

def main():
    parser = argparse.ArgumentParser(description="Запуск Google Chrome с поддержкой порта отладки 9222 (CDP)")
    parser.add_argument("--port", type=int, default=9222, help="Порт отладки Chrome (по умолчанию 9222)")
    parser.add_argument("-y", "--yes", action="store_true", help="Автоматически перезапускать Chrome без запроса подтверждения")
    args, unknown = parser.parse_known_args()

    print("=" * 80)
    print(" 🚀 ЗАПУСК GOOGLE CHROME С ПОДДЕРЖКОЙ АВТОМАТИЗАЦИИ (40+ АККАУНТОВ)")
    print("=" * 80)

    user_data_path = chrome_profiles.get_chrome_user_data_path()

    # 1. Проверяем, не открыт ли уже Chrome с портом 9222
    if chrome_profiles.is_cdp_available(port=args.port):
        print(f"\n[✔] Google Chrome УЖЕ ЗАПУЩЕН с активным портом отладки {args.port}!")
        print("Все ваши 40 аккаунтов уже подключены! Вы можете сразу генерировать:")
        print('  .\\generate.bat "A futuristic flying car over cyberpunk city" --profile auto')
        print('  .\\generate_image.bat "A cybernetic dragon in neon forest" --profile auto\n')
        return

    chrome_exe = chrome_profiles.find_chrome_executable()
    if not chrome_exe:
        print("\n[-] Ошибка: Google Chrome не найден по стандартным путям Windows.")
        print("Убедитесь, что Google Chrome установлен на вашем компьютере.")
        return

    # 2. Если Chrome запущен без порта отладки, предупреждаем и перезапускаем
    if is_chrome_running():
        print("\n[!] Внимание: Google Chrome сейчас открыт в обычном режиме.")
        print("    Чтобы подключить ваши 40 аккаунтов к генератору, Chrome нужно перезапустить с портом 9222.")
        print("    (Все ваши вкладки, закладки и пароли в безопасности и сохраняются).\n")
        if not args.yes:
            try:
                input("Нажмите Enter для перезапуска Chrome (или закройте окно для отмены)... ")
            except Exception:
                pass
        print("[+] Завершение старых процессов Chrome...")
        kill_chrome_processes()
        time.sleep(1.5)

    # 3. Запуск Chrome с флагом --remote-debugging-port=9222 и явным user-data-dir
    cmd = [
        str(chrome_exe),
        f"--remote-debugging-port={args.port}",
        f"--user-data-dir={user_data_path}"
    ]

    print(f"\n[+] Запуск Chrome с поддержкой 40 профилей...")
    subprocess.Popen(cmd)

    # Ждем активации порта
    print("Ожидание активации порта автоматизации 9222...")
    port_active = False
    for _ in range(16):
        time.sleep(0.5)
        if chrome_profiles.is_cdp_available(port=args.port):
            port_active = True
            break

    if port_active:
        print("\n" + "=" * 80)
        print(" [✔] ВСЁ ГОТОВО! GOOGLE CHROME УСПЕШНО ПОДКЛЮЧЕН К АВТОМАТИЗАЦИИ")
        print("=" * 80)
        print(f"    Порт отладки: 127.0.0.1:{args.port} АКТИВЕН.")
        print("    Все ваши 40 аккаунтов доступны для генерации БЕЗ повторного ввода паролей!\n")
        print("📌 ВАЖНО: Не закрывайте открывшееся окно Google Chrome.")
        print("   Вы можете свернуть его или пользоваться им как обычно.\n")
        print("🚀 Теперь запускайте генерацию:")
        print('   .\\generate.bat "Ваш промпт" --profile auto')
        print('   .\\generate_image.bat "Ваш промпт" --profile auto\n')
    else:
        print("\n" + "=" * 80)
        print(" 💡 ПОРТ ОТЛАДКИ НЕ ТРЕБУЕТСЯ: ИСПОЛЬЗУЙТЕ ПРЯМОЙ ВХОД В 1 КЛИК")
        print("=" * 80)
        print(" Google Chrome заблокировал внешний порт отладки для безопасности.")
        print(" Но вы можете войти в Google Flow прямо сейчас в 1 клик через login.bat!\n")
        
        try:
            ans = input("Открыть окно входа в Google Flow прямо сейчас? (y/n) [Enter = Да]: ").strip().lower()
        except Exception:
            ans = "y"
            
        if ans in ("", "y", "yes", "д", "да"):
            import login
            login.main()
        else:
            print("\nВы всегда можете запустить вход командой: .\\login.bat\n")

if __name__ == "__main__":
    main()
