"""
Скрипт автоматического захвата и управления сессиями Google Flow (40+ профилей).
Запускает ваш НАСТОЯЩИЙ профиль Chrome (без режима гостя и без конфликтов),
автоматически вытягивает куки Flow напрямую из памяти браузера (без расширений)
и сразу же переходит к следующему профилю.
"""
import sys
import os
import json
import time
import ctypes
from ctypes import wintypes
import re
import urllib.request
import argparse
import threading
import subprocess
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))
import chrome_profiles

# Win32 API константы для чтения памяти Chrome
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_READWRITE = 0x04
PAGE_READONLY = 0x02

kernel32 = ctypes.windll.kernel32

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("PartitionId", wintypes.WORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]

# Регулярные выражения для поиска токенов сессий NextAuth в RAM
TOKEN_REGEX = re.compile(rb"(?:__Secure-next-auth\.session-token|next-auth\.session-token)=([a-zA-Z0-9_\-\.]{50,4500})")
JWE_REGEX = re.compile(rb"eyJhbGciOi[a-zA-Z0-9_\-\.]{300,4500}")

# Глобальное состояние для приема токена от локального сервера
_token_lock = threading.Lock()
_latest_received_token = None
_token_event = threading.Event()

class TokenReceiverHandler(BaseHTTPRequestHandler):
    """Принимает токен из браузера через HTTP запрос."""
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
        except Exception:
            self.send_response(400)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        pass

def start_local_token_server(port: int = 9876) -> HTTPServer:
    """Запускает фоновый HTTP-сервер для приема токенов."""
    server = HTTPServer(("127.0.0.1", port), TokenReceiverHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    return server

def get_clipboard_text() -> str:
    """Читает текст из буфера обмена Windows."""
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

def open_real_chrome_profile(folder: str, url: str = "https://labs.google/fx/tools/flow") -> bool:
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

def verify_token(token: str) -> tuple[bool, str]:
    """Проверяет токен через официальный API labs.google и возвращает (валиден, email)."""
    token = clean_token_string(token)
    if not token or len(token) < 50:
        return False, ""
    try:
        req = urllib.request.Request("https://labs.google/fx/api/auth/session")
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
        req.add_header("Cookie", f"__Secure-next-auth.session-token={token}")
        req.add_header("Accept", "application/json")
        req.add_header("Referer", "https://flow.google.com/")
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode())
            if data and data.get("user") and data.get("user", {}).get("email"):
                return True, data["user"]["email"]
    except Exception:
        pass
    return False, ""

def save_session_from_token(folder: str, token: str, extra_cookies: Optional[list[dict]] = None) -> tuple[bool, str]:
    """Сохраняет токен сессии и сопутствующие куки в файл .flow_sessions/."""
    token = clean_token_string(token)
    if not token or len(token) < 20:
        return False, ""

    session_file = chrome_profiles.get_session_file(folder)
    session_file.parent.mkdir(parents=True, exist_ok=True)
    
    cookies = [{
        "name": "__Secure-next-auth.session-token",
        "value": token,
        "domain": "labs.google",
        "path": "/",
        "expires": -1,
        "httpOnly": True,
        "secure": True,
        "sameSite": "Lax"
    }]

    if extra_cookies:
        cookies.extend(extra_cookies)
    elif session_file.exists():
        try:
            old_data = json.loads(session_file.read_text(encoding="utf-8"))
            for c in old_data.get("cookies", []):
                if c.get("name") != "__Secure-next-auth.session-token":
                    cookies.append(c)
        except Exception:
            pass

    state = {
        "cookies": cookies,
        "origins": [
            {"origin": "https://flow.google.com", "localStorage": []},
            {"origin": "https://labs.google", "localStorage": []}
        ]
    }
    session_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    
    verified, user_email = chrome_profiles.verify_session(folder)
    if verified:
        return True, user_email or ""
    return False, ""

def get_priority_chrome_pids() -> list[int]:
    """Возвращает PID активных процессов Chrome с приоритетом для NetworkService."""
    try:
        ps_cmd = """
        Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'chrome.exe' } | ForEach-Object {
            [PSCustomObject]@{
                Id = $_.ProcessId
                Cmd = $_.CommandLine
            }
        } | ConvertTo-Json -Compress
        """
        res = subprocess.check_output(['powershell', '-NoProfile', '-Command', ps_cmd], text=True).strip()
        if not res:
            return []
        data = json.loads(res)
        if isinstance(data, dict):
            data = [data]
        
        network_pids = []
        browser_pids = []
        other_pids = []

        for item in data:
            pid = item.get("Id")
            cmd = item.get("Cmd") or ""
            if "network.mojom.NetworkService" in cmd:
                network_pids.append(pid)
            elif "--type=" not in cmd:
                browser_pids.append(pid)
            else:
                other_pids.append(pid)
        
        return network_pids + browser_pids + other_pids
    except Exception:
        try:
            res = subprocess.check_output(['powershell', '-NoProfile', '-Command', '(Get-Process chrome -ErrorAction SilentlyContinue).Id'], text=True)
            return [int(x.strip()) for x in res.split() if x.strip().isdigit()]
        except Exception:
            return []

def scan_chrome_memory_for_flow_session(pids: list[int], known_invalid: set[str], expected_email: str = "") -> tuple[str, str]:
    """
    Быстро сканирует память процессов Chrome на наличие токенов сессии Google Flow.
    Возвращает (токен, email) или ("", "").
    """
    mbi = MEMORY_BASIC_INFORMATION()
    mbi_size = ctypes.sizeof(mbi)

    for pid in pids:
        handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not handle:
            continue
        address = 0
        while kernel32.VirtualQueryEx(handle, ctypes.c_void_p(address), ctypes.byref(mbi), mbi_size):
            if mbi.State == MEM_COMMIT and (mbi.Protect & (PAGE_READWRITE | PAGE_READONLY)):
                size = mbi.RegionSize
                if 4096 <= size <= 10 * 1024 * 1024:
                    buf = ctypes.create_string_buffer(size)
                    bytes_read = ctypes.c_size_t()
                    if kernel32.ReadProcessMemory(handle, ctypes.c_void_p(address), buf, size, ctypes.byref(bytes_read)):
                        data = buf.raw[:bytes_read.value]
                        if b"session-token" in data or b"labs.google" in data:
                            # 1. Поиск присвоения куки в HTTP-заголовках сетевой службы
                            for m in TOKEN_REGEX.finditer(data):
                                raw = m.group(1).decode("latin1", errors="ignore")
                                cand = re.split(r'[^a-zA-Z0-9_\-\.]', raw)[0]
                                if cand and cand not in known_invalid:
                                    ok, auth_email = verify_token(cand)
                                    if ok:
                                        if expected_email and auth_email.lower() != expected_email.lower():
                                            known_invalid.add(cand)
                                            continue
                                        kernel32.CloseHandle(handle)
                                        return cand, auth_email
                                    else:
                                        known_invalid.add(cand)

                            # 2. Поиск JWE структуры токена
                            if b"labs.google" in data:
                                for m in JWE_REGEX.finditer(data):
                                    raw = m.group(0).decode("latin1", errors="ignore")
                                    cand = re.split(r'[^a-zA-Z0-9_\-\.]', raw)[0]
                                    if cand and cand not in known_invalid and len(cand) > 300:
                                        ok, auth_email = verify_token(cand)
                                        if ok:
                                            if expected_email and auth_email.lower() != expected_email.lower():
                                                known_invalid.add(cand)
                                                continue
                                            kernel32.CloseHandle(handle)
                                            return cand, auth_email
                                        else:
                                            known_invalid.add(cand)
            address += mbi.RegionSize
            if address >= 0x7FFFFFFF0000:
                break
        kernel32.CloseHandle(handle)

    return "", ""

def capture_session_for_profile(
    folder: str,
    display_name: str,
    email: str = "",
    force: bool = False,
    timeout_sec: int = 60
) -> bool:
    """
    Открывает настоящий профиль Chrome, ждет входа в Google Flow,
    автоматически вытягивает куки из памяти и переходит к следующему профилю.
    """
    global _latest_received_token
    session_file = chrome_profiles.get_session_file(folder)
    is_valid, user_email = chrome_profiles.verify_session(folder)

    if is_valid and not force:
        print(f"[✔] Профиль '{folder}' ({display_name}) УЖЕ АВТОРИЗОВАН ({chrome_profiles.mask_email(user_email or email)}). Пропуск.")
        return True

    print("\n" + "=" * 80)
    print(f" 🚀 АВТОВХОД И ЗАХВАТ СЕССИИ: {folder} ({display_name})")
    print("=" * 80)
    masked = chrome_profiles.mask_email(email)
    if masked:
        print(f"    Google Email : {masked}")
    print(f"    Файл сессии  : {session_file.name}")
    print("[+] Открываем Google Flow в вашем настоящем Chrome под этим профилем...")

    with _token_lock:
        _latest_received_token = None
    _token_event.clear()

    initial_clip = get_clipboard_text()
    known_invalid = set()

    # Защита от перекрестного захвата: исключаем токены из всех ДРУГИХ профилей
    for other_p in chrome_profiles.get_all_chrome_profiles():
        if other_p["folder"] != folder:
            other_sess = chrome_profiles.get_session_file(other_p["folder"])
            if other_sess.exists():
                try:
                    sdata = json.loads(other_sess.read_text(encoding="utf-8"))
                    for c in sdata.get("cookies", []):
                        val = c.get("value")
                        if val:
                            known_invalid.add(val)
                except Exception:
                    pass

    # Открываем настоящий Chrome под нужным профилем
    open_real_chrome_profile(folder, "https://flow.google.com/")

    print("\n[i] Ожидание входа в Google Flow...")
    print("    💡 Если страница попросит войти — нажмите 'Войти' (Sign in) в окне Chrome.")
    print("    ✨ Как только Flow откроется, скрипт САМ подтянет куки и сразу перейдет к следующему профилю!\n")

    start_time = time.time()
    last_clip = initial_clip
    last_dot_time = time.time()

    while time.time() - start_time < timeout_sec:
        # 1. Проверяем токен напрямую из памяти Chrome (NetworkService & Browser RAM)
        pids = get_priority_chrome_pids()
        if pids:
            cand_token, auth_email = scan_chrome_memory_for_flow_session(pids, known_invalid, expected_email=email)
            if cand_token:
                saved_ok, auth_email = save_session_from_token(folder, cand_token)
                if saved_ok:
                    print("\n" + "=" * 80)
                    print(f" [✔] СЕССИЯ ДЛЯ '{folder}' АВТОМАТИЧЕСКИ ЗАХВАЧЕНА ИЗ ПАМЯТИ CHROME!")
                    print(f"     Аккаунт : {chrome_profiles.mask_email(auth_email or email)}")
                    print(f"     Файл    : {session_file.name}")
                    print("     ✔ Сессия проверена! Сразу переходим к следующему профилю...")
                    print("=" * 80)
                    return True

        # 2. Проверяем HTTP сервер
        with _token_lock:
            if _latest_received_token:
                candidate = _latest_received_token
                _latest_received_token = None
                if candidate not in known_invalid:
                    ok, auth_email = verify_token(candidate)
                    if ok and (not email or auth_email.lower() == email.lower()):
                        saved_ok, auth_email = save_session_from_token(folder, candidate)
                        if saved_ok:
                            print("\n" + "=" * 80)
                            print(f" [✔] СЕССИЯ ДЛЯ '{folder}' ПОЛУЧЕНА И СОХРАНЕНА!")
                            print(f"     Аккаунт : {chrome_profiles.mask_email(auth_email or email)}")
                            print(f"     Файл    : {session_file.name}")
                            print("     ✔ Сессия проверена! Сразу переходим к следующему профилю...")
                            print("=" * 80)
                            return True
                    else:
                        known_invalid.add(candidate)

        # 3. Проверяем буфер обмена Windows (если пользователь скопировал токен)
        current_clip = get_clipboard_text()
        if current_clip and current_clip != last_clip:
            cleaned = clean_token_string(current_clip)
            if len(cleaned) > 25 and ("ey" in cleaned[:10] or "auth" in current_clip.lower()) and cleaned not in known_invalid:
                ok, auth_email = verify_token(cleaned)
                if ok and (not email or auth_email.lower() == email.lower()):
                    saved_ok, auth_email = save_session_from_token(folder, cleaned)
                    if saved_ok:
                        print("\n" + "=" * 80)
                        print(f" [✔] КУКИ ДЛЯ '{folder}' ЗАХВАЧЕНЫ ИЗ БУФЕРА ОБМЕНА!")
                        print(f"     Аккаунт : {chrome_profiles.mask_email(auth_email or email)}")
                        print(f"     Файл    : {session_file.name}")
                        print("     ✔ Сессия проверена! Сразу переходим к следующему профилю...")
                        print("=" * 80)
                        return True
                else:
                    known_invalid.add(cleaned)
            last_clip = current_clip

        # Индикатор ожидания
        if time.time() - last_dot_time >= 2.0:
            elapsed = int(time.time() - start_time)
            rem = timeout_sec - elapsed
            print(f"    ⏳ Ожидание активности Flow в браузере... (осталось {rem} сек)", end="\r", flush=True)
            last_dot_time = time.time()

        time.sleep(1.0)

    print(f"\n[!] Время ожидания для профиля '{folder}' истекло ({timeout_sec} сек).")
    try:
        manual = input("Вставьте токен вручную (или нажмите Enter для перехода к следующему): ").strip()
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

    # Запускаем локальный HTTP-сервер
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

    # 2. Выбор профиля или пакетный вход
    if not profile_selector and not args.all:
        print("\n" + "=" * 80)
        print(" [?] ВЫБОР ПРОФИЛЯ ДЛЯ ВХОДА:")
        print("     - Введите номер строки (#1..#N) или номер профиля (например: 1, 2, 7, 10, 34)")
        print("     - Введите имя профиля (например: Default, Profile 2, GeminiPro)")
        print("     - Введите 'all' для последовательного входа во ВСЕ профили по очереди")
        print("     - Нажмите Enter для выхода")
        print("=" * 80)
        try:
            choice = input("\n👉 Ваш выбор: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nВыход.")
            return

        if not choice:
            print("Выход.")
            return

        if choice.lower() in ("all", "все", "a"):
            run_all = True
        else:
            profile_selector = choice
            run_all = False
    else:
        run_all = bool(args.all)

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
        print("   1. Скрипт по очереди открывает каждый профиль в вашем Chrome.")
        print("   2. Вы заходите в Google Flow (или просто открываете страницу).")
        print("   3. Скрипт САМ вытягивает сессию и СРАЗУ переходит к следующему профилю!")
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
        if p["folder"].lower() == chosen_folder.lower():
            chosen_name = p["name"]
            chosen_email = p.get("email", "")
            chosen_folder = p["folder"]
            break

    capture_session_for_profile(
        chosen_folder,
        chosen_name,
        chosen_email,
        force=args.force,
        timeout_sec=args.timeout
    )
    return

if __name__ == "__main__":
    main()
