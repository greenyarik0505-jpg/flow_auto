"""
Скрипт автоматического захвата и управления сессиями Google Flow (40+ профилей).
Запускает ваш НАСТОЯЩИЙ профиль Chrome (без режима гостя и без конфликтов),
автоматически вытягивает куки Flow и сразу же переходит к следующему профилю.
"""
import sys
import os
import json
import time
import asyncio
import argparse
import threading
import subprocess
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import chrome_profiles

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).parent.resolve()

# Глобальное состояние для приема токена от расширения через HTTP
_token_lock = threading.Lock()
_latest_received_token = None
_token_event = threading.Event()

class TokenReceiverHandler(BaseHTTPRequestHandler):
    """Принимает токен из Chrome-расширения flow_extension."""
    def do_POST(self):
        global _latest_received_token
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8", errors="replace")
            data = json.loads(body)
            raw_token = data.get("token", "").strip()
            if raw_token and len(raw_token) > 20:
                with _token_lock:
                    _latest_received_token = raw_token
                _token_event.set()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        except Exception as e:
            self.send_response(400)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        # Отключаем спам в консоль от встроенного сервера
        pass

def start_local_token_server(port: int = 9876) -> HTTPServer:
    """Запускает фоновый HTTP-сервер для приема токенов из браузера."""
    server = HTTPServer(("127.0.0.1", port), TokenReceiverHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    return server

def get_clipboard_text() -> str:
    """Читает текст из буфера обмена Windows через PowerShell."""
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=2
        )
        return res.stdout.strip()
    except Exception:
        return ""

def open_real_chrome_profile(folder: str, url: str = "https://flow.google.com/") -> bool:
    """
    Открывает НАСТОЯЩИЙ профиль пользователя в Google Chrome.
    Никакого режима гостя: все сохраненные аккаунты, пароли и закладки на месте.
    """
    chrome_exe = chrome_profiles.find_chrome_executable()
    if not chrome_exe:
        print("[-] Ошибка: Google Chrome не найден по стандартным путям.")
        return False
    
    cmd = [str(chrome_exe), f"--profile-directory={folder}", url]
    try:
        subprocess.Popen(cmd)
        return True
    except Exception as e:
        print(f"[-] Ошибка запуска Google Chrome: {e}")
        return False

def clean_token_string(token: str) -> str:
    """Очищает строку токена от кавычек и префиксов cookie."""
    token = token.strip().strip('"').strip("'")
    if "=" in token and "__Secure" in token:
        for part in token.split(";"):
            part = part.strip()
            if part.startswith("__Secure-next-auth.session-token="):
                token = part.split("=", 1)[1].strip()
                break
    return token

def save_session_from_token(folder: str, token: str) -> tuple[bool, str]:
    """
    Сохраняет сессию Google Flow из токена __Secure-next-auth.session-token
    и проверяет её валидность через официальный API.
    """
    token = clean_token_string(token)
    if not token or len(token) < 20:
        return False, ""

    session_file = chrome_profiles.get_session_file(folder)
    session_file.parent.mkdir(parents=True, exist_ok=True)
    cookie_entry = {
        "name": "__Secure-next-auth.session-token",
        "value": token,
        "domain": "labs.google",
        "path": "/",
        "expires": -1,
        "httpOnly": True,
        "secure": True,
        "sameSite": "Lax"
    }
    state = {
        "cookies": [cookie_entry],
        "origins": [{"origin": "https://labs.google", "localStorage": []}]
    }
    session_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    
    verified, user_email = chrome_profiles.verify_session(folder)
    if verified:
        return True, user_email or ""
    return False, ""

def capture_session_for_profile(
    folder: str,
    display_name: str,
    email: str = "",
    force: bool = False,
    timeout_sec: int = 60
) -> bool:
    """
    Открывает профиль в Chrome, ждет входа в Flow, автоматически вытягивает куки
    и завершает работу для немедленного перехода к следующему профилю.
    """
    global _latest_received_token
    session_file = chrome_profiles.get_session_file(folder)
    is_valid, user_email = chrome_profiles.verify_session(folder)

    if is_valid and not force:
        print(f"[✔] Профиль '{folder}' ({display_name}) УЖЕ АВТОРИЗОВАН ({chrome_profiles.mask_email(user_email or email)}). Пропуск.")
        return True

    print("\n" + "=" * 80)
    print(f" 🚀 ВХОД И ЗАХВАТ КУКОВ: {folder} ({display_name})")
    print("=" * 80)
    masked = chrome_profiles.mask_email(email)
    if masked:
        print(f"    Google Email : {masked}")
    print(f"    Файл сессии  : {session_file.name}")
    print("[+] Открываем Google Flow в вашем настоящем Chrome под этим профилем...")

    # Сбрасываем предыдущий токен
    with _token_lock:
        _latest_received_token = None
    _token_event.clear()

    # Запоминаем текущий буфер обмена, чтобы не поймать старый токен от прошлого профиля
    initial_clip = get_clipboard_text()

    open_real_chrome_profile(folder, "https://flow.google.com/")

    print("\n[i] Ожидание входа в Google Flow и захвата куков...")
    print("    👉 Если расширение Flow Auto Sync установлено в Chrome — токен уйдет сам!")
    print("    👉 Или нажмите на значок расширения в Chrome ➔ 'Скопировать и отправить'")
    print("    👉 Или скопируйте в DevTools F12 (значение куки __Secure-next-auth.session-token)")
    print("    (Как только токен будет получен, скрипт САМ сохранится и перейдет дальше!)\n")

    start_time = time.time()
    last_clip = initial_clip

    while time.time() - start_time < timeout_sec:
        # 1. Проверяем токен от HTTP-сервера (из расширения)
        with _token_lock:
            if _latest_received_token:
                candidate = _latest_received_token
                _latest_received_token = None
                saved_ok, auth_email = save_session_from_token(folder, candidate)
                if saved_ok:
                    print("=" * 80)
                    print(f" [✔] КУКИ ДЛЯ '{folder}' АВТОМАТИЧЕСКИ ПОЛУЧЕНЫ ИЗ БРАУЗЕРА!")
                    print(f"     Аккаунт : {chrome_profiles.mask_email(auth_email or email)}")
                    print(f"     Файл    : {session_file.name}")
                    print("     ✔ Сессия проверена! Сразу переходим к следующему профилю...")
                    print("=" * 80)
                    return True

        # 2. Проверяем буфер обмена Windows (если пользователь скопировал токен)
        current_clip = get_clipboard_text()
        if current_clip and current_clip != last_clip:
            cleaned = clean_token_string(current_clip)
            if len(cleaned) > 25 and ("ey" in cleaned[:10] or "auth" in current_clip.lower()):
                saved_ok, auth_email = save_session_from_token(folder, cleaned)
                if saved_ok:
                    print("=" * 80)
                    print(f" [✔] КУКИ ДЛЯ '{folder}' УСПЕШНО ЗАХВАЧЕНЫ ИЗ БУФЕРА ОБМЕНА!")
                    print(f"     Аккаунт : {chrome_profiles.mask_email(auth_email or email)}")
                    print(f"     Файл    : {session_file.name}")
                    print("     ✔ Сессия проверена! Сразу переходим к следующему профилю...")
                    print("=" * 80)
                    return True
            last_clip = current_clip

        time.sleep(0.5)

    print(f"\n[!] Время ожидания для профиля '{folder}' истекло ({timeout_sec} сек).")
    try:
        manual = input("Вставьте токен вручную (или Enter для перехода к следующему): ").strip()
        if manual:
            saved_ok, auth_email = save_session_from_token(folder, manual)
            if saved_ok:
                print(f"[✔] Сессия успешно сохранена для '{folder}'!")
                return True
    except (KeyboardInterrupt, EOFError):
        pass

    return False

def main():
    parser = argparse.ArgumentParser(description="Google Flow: Авторизация аккаунтов Chrome (40+ профилей)")
    parser.add_argument("profile", type=str, nargs="?", default=None, help="Номер или имя профиля (например: 2, 'Profile 2')")
    parser.add_argument("token_pos", type=str, nargs="?", default=None, help="Токен сессии (опционально: login.bat 2 <token>)")
    parser.add_argument("--profile", dest="profile_opt", type=str, default=None, help="Имя или номер профиля")
    parser.add_argument("--token", type=str, default=None, help="Вставить готовый токен __Secure-next-auth.session-token напрямую")
    parser.add_argument("--all", action="store_true", help="Авторизовать все доступные профили Chrome по очереди")
    parser.add_argument("--list", action="store_true", help="Только показать статус сессий всех профилей")
    parser.add_argument("--force", action="store_true", help="Принудительно перезаписать сессию, даже если она уже валидна")
    parser.add_argument("--timeout", type=int, default=60, help="Таймаут ожидания входа в каждый профиль в секундах (по умолчанию 60)")
    args = parser.parse_args()

    profile_selector = args.profile or args.profile_opt
    direct_token = args.token or args.token_pos

    profiles = chrome_profiles.get_all_chrome_profiles()
    if not profiles:
        print("[-] Профили Chrome не найдены.")
        return

    print("=" * 80)
    print(" 🚀 GOOGLE FLOW: СТАТУС СЕССИЙ АККАУНТОВ (40+ ПРОФИЛЕЙ)")
    print("=" * 80)
    print(f"Каталог данных Chrome: {chrome_profiles.get_chrome_user_data_path()}\n")

    print(f"{'#':<3} | {'Папка':<12} | {'Имя в Chrome':<20} | {'Email':<22} | {'Сессия Flow'}")
    print("-" * 80)

    for idx, p in enumerate(profiles, start=1):
        folder = p["folder"]
        name = p["name"][:18]
        email = chrome_profiles.mask_email(p["email"]) or "(локальный)"
        if len(email) > 20:
            email = email[:19] + "…"
        
        is_verified, verified_email = chrome_profiles.verify_session(folder)
        if is_verified:
            status = "✔ ГОТОВ К РАБОТЕ"
        elif chrome_profiles.get_session_file(folder).exists():
            status = "⏳ ТРЕБУЕТ ОБНОВЛЕНИЯ"
        else:
            status = "⏳ НУЖЕН ВХОД"
        print(f"{idx:<3} | {folder:<12} | {name:<20} | {email:<22} | {status}")
    print("-" * 80)

    if args.list:
        return

    # Запускаем локальный HTTP-сервер для мгновенного приема куков от расширения
    try:
        start_local_token_server(9876)
    except Exception:
        pass

    # 1. Если токен передан напрямую аргументом
    if direct_token:
        chosen_folder = chrome_profiles.resolve_profile_folder(profile_selector or "Default")
        saved_ok, auth_email = save_session_from_token(chosen_folder, direct_token)
        if saved_ok:
            print(f"[✔] Сессия успешно сохранена для {chosen_folder} ({chrome_profiles.mask_email(auth_email)})!")
        else:
            print("[-] Ошибка валидации токена.")
        return

    # 2. Пакетная авторизация всех профилей (--all или если профиль не указан)
    run_all = args.all or (not profile_selector)

    if run_all:
        unauthorized = [p for p in profiles if not chrome_profiles.verify_session(p["folder"])[0] or args.force]
        if not unauthorized:
            print("\n[✔] ВСЕ профили Chrome уже авторизованы и готовы к генерации!")
            print("Вы можете сразу генерировать:")
            print('  .\\generate.bat "Ваш промпт" --profile auto')
            print('  .\\generate_image.bat "Ваш промпт" --profile auto\n')
            return

        print(f"\n[+] Будет выполнена авторизация {len(unauthorized)} профилей по очереди.")
        print("💡 Как это работает:")
        print("   1. Скрипт открывает каждый профиль в вашем Chrome.")
        print("   2. Вы заходите в Google Flow (или куки подтягиваются автоматически).")
        print("   3. Скрипт сразу вытягивает куки и САМ переходит к следующему профилю!")
        print("-" * 80)

        for i, p in enumerate(unauthorized, start=1):
            print(f"\n>>> ШАГ {i} ИЗ {len(unauthorized)}: {p['folder']} ({p['name']}) <<<")
            success = capture_session_for_profile(
                p["folder"],
                p["name"],
                p.get("email", ""),
                force=args.force,
                timeout_sec=args.timeout
            )
            if success:
                time.sleep(1)

        print("\n" + "=" * 80)
        print(" 🎉 ОБРАБОТКА ВСЕХ ПРОФИЛЕЙ ЗАВЕРШЕНА!")
        print("=" * 80)
        print("Все активные аккаунты сохранены в .flow_sessions/ и готовы к генерации в фоне.")
        print('Запуск генерации: .\\generate.bat "Промпт" --profile auto\n')
        return

    # 3. Одиночная авторизация конкретного профиля
    chosen_folder = chrome_profiles.resolve_profile_folder(profile_selector)
    chosen_name = chosen_folder
    chosen_email = ""
    for p in profiles:
        if p["folder"] == chosen_folder:
            chosen_name = p["name"]
            chosen_email = p.get("email", "")
            break

    capture_session_for_profile(
        chosen_folder,
        chosen_name,
        chosen_email,
        force=args.force,
        timeout_sec=args.timeout
    )

if __name__ == "__main__":
    main()
