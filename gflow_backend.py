"""
Официальный надежный бэкенд Google Flow на базе gflow CLI.
Использует настоящие persistent Chromium/Chrome профили со SQLite БД,
что исключает блокировки и детекты Google.
"""
import sys
import os
import json
import time
import re
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).parent.resolve()
VENV_GFLOW = BASE_DIR / ".venv" / "Scripts" / "gflow.exe"
LIMITS_FILE = BASE_DIR / ".flow_limits.json"

def get_gflow_bin() -> str:
    """Возвращает путь к исполняемому файлу gflow.exe."""
    if VENV_GFLOW.exists():
        return str(VENV_GFLOW)
    return "gflow"

def load_limits() -> Dict[str, Any]:
    if LIMITS_FILE.exists():
        try:
            return json.loads(LIMITS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_limits(data: Dict[str, Any]) -> None:
    try:
        LIMITS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

def mark_profile_exhausted(profile: str, reason: str = "Лимит генераций исчерпан", cooldown_hours: float = 12.0) -> None:
    data = load_limits()
    cooldown_until = time.time() + (cooldown_hours * 3600)
    data[profile] = {
        "exhausted_at": time.time(),
        "cooldown_until": cooldown_until,
        "reason": reason
    }
    save_limits(data)

def get_exhausted_profiles() -> Dict[str, Any]:
    data = load_limits()
    now = time.time()
    active = {}
    changed = False
    for prof, entry in list(data.items()):
        if now < entry.get("cooldown_until", 0):
            active[prof] = entry
        else:
            del data[prof]
            changed = True
    if changed:
        save_limits(data)
    return active

def reset_limits(profile: Optional[str] = None) -> None:
    if profile:
        data = load_limits()
        if profile in data:
            del data[profile]
            save_limits(data)
    else:
        if LIMITS_FILE.exists():
            try:
                LIMITS_FILE.unlink()
            except Exception:
                pass

def normalize_profile_name(selector: Optional[str]) -> str:
    """Приводит варианты ввода (1, 10, 'Profile 10', 'p10', '#10', 'Default') к каноническому имени профиля gflow."""
    if not selector:
        return "auto"
    s = str(selector).strip()
    if s.lower() in ("auto", "rotate", "next"):
        return "auto"
    if s.lower() in ("default", "def"):
        return "1"
    m = re.match(r"^(?:profile\s*|p|#)(\d+)$", s, re.IGNORECASE)
    if m:
        return m.group(1)
    return s

def list_profiles() -> List[Dict[str, Any]]:
    """Возвращает актуальный список всех профилей gflow со статусом сессии и лимитов."""
    try:
        from gflow_cli import profile_store
        raw_profiles = profile_store.list_profiles()
    except Exception:
        raw_profiles = []

    exhausted = get_exhausted_profiles()
    result = []
    for p in raw_profiles:
        name = p.name
        is_ex = name in exhausted
        result.append({
            "name": name,
            "dir": p.profile_dir,
            "has_cookies": p.cookies_present,
            "email": p.google_account or "",
            "is_default": p.is_default,
            "is_exhausted": is_ex,
            "cooldown_until": exhausted[name].get("cooldown_until") if is_ex else None,
            "exhausted_reason": exhausted[name].get("reason", "") if is_ex else None,
        })
    return result

def check_profile_status(profile: str) -> tuple[bool, str]:
    """Проверяет валидность сессии профиля через gflow auth status."""
    clean = normalize_profile_name(profile)
    cmd = [get_gflow_bin(), "auth", "status", "--profile", clean]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode == 0:
            return True, "Авторизован и проверен"
        out = (res.stdout + " " + res.stderr).strip()
        if "has no session" in out:
            return False, "Нет сессии (требуется вход)"
        elif "expired" in out.lower():
            return False, "Сессия истекла"
        return False, "Не авторизован"
    except Exception as e:
        return False, f"Ошибка проверки: {e}"

def get_unified_profiles() -> List[Dict[str, Any]]:
    """
    Возвращает объединенный список профилей:
    1. Все аккаунты Google Chrome, обнаруженные на компьютере.
    2. Все сохраненные persistent-профили gflow CLI.
    """
    import chrome_profiles
    chrome_profs = chrome_profiles.get_all_chrome_profiles()
    gflow_profs = {p["name"]: p for p in list_profiles()}
    exhausted = get_exhausted_profiles()

    unified = []
    seen_ids = set()

    for idx, cp in enumerate(chrome_profs, start=1):
        clean_id = normalize_profile_name(cp["folder"])
        seen_ids.add(clean_id)
        
        gf = gflow_profs.get(clean_id)
        is_ex = clean_id in exhausted
        
        if is_ex:
            status = "⏳ ЛИМИТ (429)"
            is_ready = False
        elif gf and gf.get("has_cookies"):
            status = "✔ ГОТОВ К РАБОТЕ"
            is_ready = True
        else:
            status = "⏳ ТРЕБУЕТСЯ ВХОД"
            is_ready = False

        unified.append({
            "num": idx,
            "id": clean_id,
            "folder": cp["folder"],
            "name": cp["name"],
            "email": cp.get("email") or (gf.get("email") if gf else "") or "(локальный)",
            "status": status,
            "is_ready": is_ready,
            "in_chrome": True,
            "in_gflow": gf is not None and bool(gf.get("has_cookies")),
        })

    for name, gf in gflow_profs.items():
        if name not in seen_ids:
            seen_ids.add(name)
            is_ex = name in exhausted
            if is_ex:
                status = "⏳ ЛИМИТ (429)"
                is_ready = False
            elif gf.get("has_cookies"):
                status = "✔ ГОТОВ К РАБОТЕ"
                is_ready = True
            else:
                status = "⏳ ТРЕБУЕТСЯ ВХОД"
                is_ready = False

            unified.append({
                "num": len(unified) + 1,
                "id": name,
                "folder": f"profile_{name}",
                "name": f"gflow #{name}",
                "email": gf.get("email") or "(вход выполнен)",
                "status": status,
                "is_ready": is_ready,
                "in_chrome": False,
                "in_gflow": True,
            })

    return unified

def find_system_chrome() -> str:
    """Определяет путь к исполняемому файлу Google Chrome."""
    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "chrome.exe"

def open_real_chrome(profile: str, url: str = "https://flow.google.com") -> bool:
    """Запускает настоящий Google Chrome с конкретным профилем пользователя, где уже выполнен вход."""
    clean_id = normalize_profile_name(profile)
    folder_name = "Default" if clean_id in ("1", "default") else f"Profile {clean_id}"
    
    disp_name = f"Профиль {clean_id}"
    email_hint = ""
    # Ищем точные данные из профилей пользователя
    try:
        for p in get_unified_profiles():
            if str(p["id"]).lower() == clean_id.lower():
                folder_name = p["folder"]
                disp_name = p["name"]
                email_hint = p.get("email", "")
                break
    except Exception:
        pass

    chrome_exe = find_system_chrome()
    cmd = [chrome_exe, f"--profile-directory={folder_name}", url]
    print("\n" + "=" * 80)
    print(f" 🚀 ОТКРЫТИЕ ВАШЕГО НАСТОЯЩЕГО GOOGLE CHROME")
    print("=" * 80)
    print(f"    Профиль в Chrome : {folder_name} ({disp_name})")
    if email_hint and email_hint != "(локальный)":
        print(f"    Google Аккаунт   : {email_hint}")
    print(f"    Целевой сайт     : {url}")
    print("=" * 80)
    print(" [i] Запуск прямого сеанса Chrome с вашим основным аккаунтом.")
    print("     Никаких гостей и чужих профилей — вы УЖЕ залогинены в Google!")
    print("=" * 80 + "\n")
    try:
        subprocess.Popen(cmd)
        return True
    except Exception as e:
        print(f"[-] Ошибка запуска Chrome: {e}")
        return False

def prepare_profile_container(clean_name: str, display_name: str = "", email: str = "") -> None:
    """Инициализирует профиль gflow именем и параметрами, чтобы Chrome не выглядел как гость."""
    try:
        home = Path(os.environ.get("GFLOW_CLI_HOME", Path.home() / "AppData" / "Local" / "ffroliva" / "gflow-cli"))
        p_dir = home / f"profile_{clean_name}"
        def_dir = p_dir / "Default"
        def_dir.mkdir(parents=True, exist_ok=True)
        
        name = display_name or f"Аккаунт {clean_name}"
        # 1. Local State с фиксацией Default профиля (чтобы Chrome не создавал 'Profile 2' и не открывал гостя)
        local_state_file = p_dir / "Local State"
        ls_data = {
            "profile": {
                "last_used": "Default",
                "info_cache": {
                    "Default": {
                        "name": name,
                        "user_name": email,
                        "avatar_icon": "chrome://theme/IDR_PROFILE_AVATAR_26",
                        "is_using_default_name": False
                    }
                }
            }
        }
        local_state_file.write_text(json.dumps(ls_data, ensure_ascii=False, indent=2), encoding="utf-8")

        # 2. Preferences
        pref_file = def_dir / "Preferences"
        pref_data = {
            "profile": {
                "name": name,
                "avatar_index": 26,
                "exit_type": "Normal"
            },
            "signin": {
                "allowed": True
            }
        }
        pref_file.write_text(json.dumps(pref_data, ensure_ascii=False, indent=2), encoding="utf-8")

        # 3. Удаляем случайные подпапки 'Profile X' внутри p_dir, чтобы Chrome всегда открывал Default
        for item in p_dir.iterdir():
            if item.is_dir() and item.name.startswith("Profile "):
                shutil.rmtree(item, ignore_errors=True)
    except Exception:
        pass

def login(profile: str) -> bool:
    """Запускает авторизацию указанного профиля через gflow auth login с настоящим Chrome."""
    clean_name = normalize_profile_name(profile)
    if clean_name == "auto":
        clean_name = "default"

    # Находим данные об аккаунте из Chrome
    target_info = None
    try:
        for p in get_unified_profiles():
            if str(p["id"]).lower() == clean_name.lower():
                target_info = p
                break
    except Exception:
        pass

    disp_name = target_info["name"] if target_info else f"Профиль {clean_name}"
    email_hint = target_info.get("email") if target_info else ""
    if email_hint == "(локальный)":
        email_hint = ""

    # Настраиваем контейнер, чтобы он не выглядел как 'Гость' / Person 1
    prepare_profile_container(clean_name, disp_name, email_hint)

    cmd = [get_gflow_bin(), "auth", "login", "--profile", clean_name, "--browser", "chrome"]
    print("\n" + "=" * 80)
    print(f" 🚀 АВТОРИЗАЦИЯ GOOGLE FLOW: АККАУНТ #{clean_name}")
    print("=" * 80)
    print(f"    Имя в системе : {disp_name}")
    if email_hint:
        print(f"    Google Email  : {email_hint}")
    print("=" * 80)
    print(" 💡 КАК ЭТО РАБОТАЕТ:")
    print("    1. Сейчас откроется отдельное окно Google Chrome (изолированный контейнер).")
    print("       (Это НЕ гость — сессия изолируется, чтобы 34 аккаунта не мешали друг другу).")
    if email_hint:
        print(f"    2. Нажмите 'Войти' и используйте аккаунт: {email_hint}")
    else:
        print("    2. Нажмите 'Войти' и введите данные вашего Google аккаунта.")
    print("    3. Дождитесь загрузки студии Flow (поле ввода промпта).")
    print("    4. После открытия Flow просто закройте окно Chrome.")
    print("       Сессия сохранится навсегда, повторный вход больше не потребуется!")
    print("=" * 80 + "\n")

    try:
        res = subprocess.run(cmd)
        if res.returncode == 0:
            reset_limits(clean_name)
            email = ""
            for p in list_profiles():
                if p["name"] == clean_name:
                    email = p.get("email", "")
                    break
            print("\n" + "=" * 80)
            print(f" [✔] АККАУНТ #{clean_name} УСПЕШНО АВТОРИЗОВАН!")
            if email or email_hint:
                print(f"     Google Email : {email or email_hint}")
            print("     Сессия надежно сохранена в SQLite базе данных gflow.")
            print(f"     Команда генерации видео: .\\generate.bat {clean_name} \"Ваш промпт\"")
            print(f"     Команда генерации фото:  .\\generate_image.bat {clean_name} \"Ваш промпт\"")
            print("=" * 80 + "\n")
            return True
        else:
            print(f"\n[-] Ошибка авторизации (код возврата {res.returncode}).\n")
            return False
    except Exception as e:
        print(f"\n[-] Ошибка запуска gflow: {e}\n")
        return False

def generate_video(
    prompt: str,
    model: str = "omni-flash",
    aspect: str = "16:9",
    duration: Optional[int] = None,
    out_dir: Optional[Path] = None,
    profile: Optional[str] = None,
) -> bool:
    """Генерирует видео через gflow video t2v с поддержкой авто-ротации по пулу аккаунтов."""
    out_dir = out_dir or (BASE_DIR / "output" / "videos")
    out_dir.mkdir(parents=True, exist_ok=True)
    gflow_bin = get_gflow_bin()

    prof_sel = normalize_profile_name(profile)

    # 1. Режим авто-ротации
    if prof_sel == "auto":
        profiles = list_profiles()
        valid = [p for p in profiles if p["has_cookies"] and not p["is_exhausted"]]
        if not valid:
            print("\n[!] Нет готовых профилей gflow для авто-ротации!")
            print("💡 Чтобы авторизовать аккаунт, выполните:")
            print("   .\\login.bat 1   (или любой другой номер: .\\login.bat 10)\n")
            return False

        print(f"\n[Auto-Rotation] Найдено готовых аккаунтов в пуле: {len(valid)}.")
        for idx, p in enumerate(valid, start=1):
            cand = p["name"]
            email_info = f" ({p['email']})" if p['email'] else ""
            print(f"\n[Auto-Rotation] 🚀 Попытка генерации видео через профиль '{cand}'{email_info} ({idx}/{len(valid)})...")
            cmd = [
                gflow_bin, "video", "t2v", prompt,
                "--aspect", aspect,
                "--out-dir", str(out_dir),
                "--profile", cand,
            ]
            if model:
                cmd.extend(["--model", model])
            if duration:
                cmd.extend(["--duration", str(duration)])

            res = subprocess.run(cmd)
            if res.returncode == 0:
                print(f"\n[✔] Видео успешно сгенерировано и сохранено в: {out_dir}\n")
                return True
            elif res.returncode == 4:
                print(f"\n[Auto-Rotation] ⚠️ На профиле '{cand}' закончились кредиты/квота (HTTP 429).")
                mark_profile_exhausted(cand, "Превышен лимит (429 / 0 кредитов)")
                print("[Auto-Rotation] 🔄 Автоматический переход к следующему аккаунту...")
                continue
            elif res.returncode in (3, 8):
                print(f"\n[Auto-Rotation] ⚠️ Сессия профиля '{cand}' устарела. Пропуск...")
                continue
            else:
                print(f"\n[Auto-Rotation] Ошибка генерации на '{cand}' (код {res.returncode}). Пробуем следующий...")
                continue

        print("\n[-] Все доступные аккаунты исчерпали квоту или вернули ошибку.")
        return False

    # 2. Точечный запуск на конкретном профиле
    print(f"\n[+] Запуск генерации видео через профиль '{prof_sel}'...")
    cmd = [
        gflow_bin, "video", "t2v", prompt,
        "--aspect", aspect,
        "--out-dir", str(out_dir),
        "--profile", prof_sel,
    ]
    if model:
        cmd.extend(["--model", model])
    if duration:
        cmd.extend(["--duration", str(duration)])

    res = subprocess.run(cmd)
    if res.returncode == 0:
        print(f"\n[✔] Видео успешно сгенерировано и сохранено в: {out_dir}\n")
        return True
    elif res.returncode in (2, 8):
        print(f"\n[-] Профиль '{prof_sel}' еще не авторизован в gflow!")
        print(f"💡 Для входа запустите: .\\login.bat {prof_sel}\n")
        return False
    elif res.returncode == 4:
        mark_profile_exhausted(prof_sel, "Лимит исчерпан (429)")
        print(f"\n[-] На профиле '{prof_sel}' исчерпан лимит кредитов!")
        print("💡 Используйте авто-ротацию: .\\generate.bat \"Промпт\" --profile auto\n")
        return False
    else:
        print(f"\n[-] Ошибка генерации видео (код возврата {res.returncode}).\n")
        return False

def generate_image(
    prompt: str,
    model: str = "nano-pro",
    aspect: str = "16:9",
    count: int = 1,
    out_dir: Optional[Path] = None,
    profile: Optional[str] = None,
) -> bool:
    """Генерирует фото через gflow image t2i с поддержкой авто-ротации по пулу аккаунтов."""
    out_dir = out_dir or (BASE_DIR / "output" / "images")
    out_dir.mkdir(parents=True, exist_ok=True)
    gflow_bin = get_gflow_bin()

    prof_sel = normalize_profile_name(profile)

    # 1. Режим авто-ротации
    if prof_sel == "auto":
        profiles = list_profiles()
        valid = [p for p in profiles if p["has_cookies"] and not p["is_exhausted"]]
        if not valid:
            print("\n[!] Нет готовых профилей gflow для авто-ротации!")
            print("💡 Чтобы авторизовать аккаунт, выполните:")
            print("   .\\login.bat 1   (или любой другой номер: .\\login.bat 10)\n")
            return False

        print(f"\n[Auto-Rotation] Найдено готовых аккаунтов в пуле: {len(valid)}.")
        for idx, p in enumerate(valid, start=1):
            cand = p["name"]
            email_info = f" ({p['email']})" if p['email'] else ""
            print(f"\n[Auto-Rotation] 🚀 Попытка генерации фото через профиль '{cand}'{email_info} ({idx}/{len(valid)})...")
            cmd = [
                gflow_bin, "image", "t2i", prompt,
                "--model", model,
                "--aspect", aspect,
                "-n", str(count),
                "--out", str(out_dir),
                "--profile", cand,
            ]
            res = subprocess.run(cmd)
            if res.returncode == 0:
                print(f"\n[✔] Изображения успешно созданы и сохранены в: {out_dir}\n")
                return True
            elif res.returncode == 4:
                print(f"\n[Auto-Rotation] ⚠️ На профиле '{cand}' закончились кредиты/квота (HTTP 429).")
                mark_profile_exhausted(cand, "Превышен лимит (429 / 0 кредитов)")
                print("[Auto-Rotation] 🔄 Автоматический переход к следующему аккаунту...")
                continue
            elif res.returncode in (3, 8):
                print(f"\n[Auto-Rotation] ⚠️ Сессия профиля '{cand}' устарела. Пропуск...")
                continue
            else:
                print(f"\n[Auto-Rotation] Ошибка генерации на '{cand}' (код {res.returncode}). Пробуем следующий...")
                continue

        print("\n[-] Все доступные аккаунты исчерпали квоту или вернули ошибку.")
        return False

    # 2. Точечный запуск на конкретном профиле
    print(f"\n[+] Запуск генерации фото через профиль '{prof_sel}'...")
    cmd = [
        gflow_bin, "image", "t2i", prompt,
        "--model", model,
        "--aspect", aspect,
        "-n", str(count),
        "--out", str(out_dir),
        "--profile", prof_sel,
    ]
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print(f"\n[✔] Изображения успешно сгенерированы и сохранены в: {out_dir}\n")
        return True
    elif res.returncode in (2, 8):
        print(f"\n[-] Профиль '{prof_sel}' еще не авторизован в gflow!")
        print(f"💡 Для входа запустите: .\\login.bat {prof_sel}\n")
        return False
    elif res.returncode == 4:
        mark_profile_exhausted(prof_sel, "Лимит исчерпан (429)")
        print(f"\n[-] На профиле '{prof_sel}' исчерпан лимит кредитов!")
        print("💡 Используйте авто-ротацию: .\\generate_image.bat \"Промпт\" --profile auto\n")
        return False
    else:
        print(f"\n[-] Ошибка генерации фото (код возврата {res.returncode}).\n")
        return False
