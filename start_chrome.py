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

    # 1. Проверяем, не открыт ли уже Chrome с портом 9222
    if chrome_profiles.is_cdp_available(port=args.port):
        print(f"\n[✔] Google Chrome УЖЕ ЗАПУЩЕН с активным портом отладки {args.port}!")
        print("Вы можете сразу генерировать видео и фото:")
        print('  .\\generate.bat "A futuristic flying car over cyberpunk city"')
        print('  .\\generate_image.bat "A cybernetic dragon in neon forest"\n')
        return

    chrome_exe = chrome_profiles.find_chrome_executable()
    if not chrome_exe:
        print("\n[-] Ошибка: Google Chrome не найден по стандартным путям Windows.")
        print("Убедитесь, что Google Chrome установлен на вашем компьютере.")
        return

    # 2. Если Chrome запущен без порта отладки, предупреждаем
    if is_chrome_running():
        print("\n[!] Внимание: Обнаружен запущенный Google Chrome (без порта отладки).")
        print("Чтобы активировать отладку для ваших 40 аккаунтов, Chrome необходимо перезапустить.")
        print("Закройте Chrome вручную или нажмите 'y' для автоматического перезапуска.")
        
        # Если запущено интерактивно, спрашиваем
        if sys.stdin.isatty():
            try:
                ans = input("Закрыть Chrome и перезапустить с отладкой? (y/n) [по умолчанию y]: ").strip().lower()
            except Exception:
                ans = "y"
            if ans in ("", "y", "yes", "д", "да"):
                print("[+] Завершение процессов Chrome...")
                kill_chrome_processes()
            else:
                print("[-] Запуск отменен. Пожалуйста, закройте Chrome вручную и повторите запуск.")
                return
        else:
            print("[+] Автоматический перезапуск Chrome с портом отладки...")
            kill_chrome_processes()

    # 3. Запуск Chrome с флагом --remote-debugging-port=9222
    cmd = [str(chrome_exe), "--remote-debugging-port=9222"]
    if len(sys.argv) > 1:
        cmd.extend(sys.argv[1:])

    print(f"\n[+] Запуск Chrome: {chrome_exe.name}...")
    subprocess.Popen(cmd)

    # Ждем 2-3 секунды активации порта
    print("Ожидание активации порта 9222...")
    port_active = False
    for _ in range(10):
        time.sleep(0.5)
        if chrome_profiles.is_cdp_available(port=9222):
            port_active = True
            break

    if port_active:
        print("\n[✔] Google Chrome УСПЕШНО ЗАПУЩЕН!")
        print("    Порт отладки 127.0.0.1:9222 АКТИВЕН.")
        print("    Все ваши 40 профилей, закладки и сессии доступны без повторного входа!\n")
        print("💡 Теперь можно отдавать любые команды на генерацию:")
        print('  .\\generate.bat "A futuristic flying car over cyberpunk city"')
        print('  .\\generate.bat "Cyberpunk street in rain" --profile 2')
        print('  .\\generate.bat "Nature drone shot" --profile auto  (ротация по всем 40 аккаунтам)')
        print('  .\\generate_image.bat "A cybernetic dragon in neon forest"\n')
    else:
        print("\n[!] Chrome запущен. Если порт 9222 не отвечает, убедитесь, что все старые окна Chrome были закрыты.\n")

if __name__ == "__main__":
    main()
