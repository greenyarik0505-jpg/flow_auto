"""
Модуль для работы с профилями Google Chrome.
Позволяет использовать готовые сессии и аккаунты из Google Chrome (40+ профилей)
без повторной авторизации и без конфликтов блокировки (ProcessSingleton).
"""
import os
import sys
import json
import time
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).parent.resolve()
CACHE_PROFILES_DIR = BASE_DIR / ".flow_profiles"
ROTATION_STATE_FILE = BASE_DIR / ".flow_rotation.json"
LIMITS_FILE = BASE_DIR / ".flow_limits.json"
SESSIONS_DIR = BASE_DIR / ".flow_sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

def get_session_file(profile_folder: str) -> Path:
    """Возвращает путь к сохраненному файлу состояния сессии Playwright."""
    safe_name = profile_folder.replace(" ", "_").lower()
    return SESSIONS_DIR / f"session_{safe_name}.json"

def is_profile_flow_ready(profile_folder: str) -> bool:
    """Проверяет, содержит ли сохраненная сессия рабочие куки авторизации Google Flow (OSID/SID)."""
    session_file = get_session_file(profile_folder)
    if not session_file.exists():
        return False
    try:
        data = json.loads(session_file.read_text(encoding="utf-8"))
        cookies = data.get("cookies", [])
        return any("OSID" in c.get("name", "") or "SID" in c.get("name", "") for c in cookies)
    except Exception:
        return False

class QuotaExceededError(Exception):
    """Исключение при исчерпании лимитов / кредитов / квоты аккаунта Google Flow."""
    def __init__(self, profile: str, reason: str = "Лимит генераций исчерпан"):
        self.profile = profile
        self.reason = reason
        super().__init__(f"Лимит генераций исчерпан для профиля '{profile}': {reason}")

def load_limits_state() -> Dict[str, Any]:
    """Загружает статус исчерпанных лимитов профилей."""
    if LIMITS_FILE.exists():
        try:
            return json.loads(LIMITS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_limits_state(data: Dict[str, Any]) -> None:
    """Сохраняет статус исчерпанных лимитов профилей."""
    try:
        LIMITS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

def mark_profile_exhausted(folder: str, reason: str = "Лимит исчерпан (0 кредитов)", cooldown_hours: float = 12.0) -> None:
    """Помечает профиль как исчерпавший лимит с указанием времени кулдауна (по умолчанию 12 часов)."""
    data = load_limits_state()
    now = time.time()
    cooldown_sec = cooldown_hours * 3600.0
    data[folder] = {
        "exhausted_at": now,
        "cooldown_until": now + cooldown_sec,
        "cooldown_hours": cooldown_hours,
        "reason": reason,
    }
    save_limits_state(data)

def is_profile_exhausted(folder: str) -> bool:
    """Проверяет, находится ли профиль в состоянии исчерпанного лимита."""
    data = load_limits_state()
    if folder not in data:
        return False
    entry = data[folder]
    cooldown_until = entry.get("cooldown_until", 0)
    now = time.time()
    if now >= cooldown_until:
        del data[folder]
        save_limits_state(data)
        return False
    return True

def get_exhausted_profiles() -> Dict[str, Any]:
    """Возвращает актуальный словарь всех профилей с исчерпанным лимитом (очищает истекшие)."""
    data = load_limits_state()
    now = time.time()
    active_exhausted = {}
    changed = False
    for folder, entry in list(data.items()):
        if now < entry.get("cooldown_until", 0):
            active_exhausted[folder] = entry
        else:
            del data[folder]
            changed = True
    if changed:
        save_limits_state(data)
    return active_exhausted

def reset_exhausted_limits(folder: Optional[str] = None) -> None:
    """Сбрасывает статус исчерпанных лимитов для одного или всех профилей."""
    if folder:
        data = load_limits_state()
        if folder in data:
            del data[folder]
            save_limits_state(data)
    else:
        if LIMITS_FILE.exists():
            try:
                LIMITS_FILE.unlink()
            except Exception:
                pass

def get_chrome_user_data_path(custom_path: Optional[str] = None) -> Path:
    """Возвращает путь к каталогу данных Google Chrome (User Data)."""
    if custom_path:
        p = Path(custom_path).resolve()
        if p.exists():
            return p
    
    env_custom = os.environ.get("CHROME_USER_DATA")
    if env_custom:
        p = Path(env_custom).resolve()
        if p.exists():
            return p

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        default_path = Path(local_app_data) / "Google" / "Chrome" / "User Data"
        if default_path.exists():
            return default_path

    user_home = Path.home()
    fallback = user_home / "AppData" / "Local" / "Google" / "Chrome" / "User Data"
    return fallback

def get_all_chrome_profiles(user_data_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Сканирует Google Chrome User Data и возвращает список всех обнаруженных профилей.
    Считывает имя, отображаемое название и статус наличия авторизационных данных.
    """
    if user_data_dir is None:
        user_data_dir = get_chrome_user_data_path()

    if not user_data_dir.exists():
        return []

    local_state_file = user_data_dir / "Local State"
    info_cache: Dict[str, Any] = {}

    if local_state_file.exists():
        try:
            content = local_state_file.read_text(encoding="utf-8", errors="ignore")
            data = json.loads(content)
            info_cache = data.get("profile", {}).get("info_cache", {})
        except Exception:
            pass

    profiles: List[Dict[str, Any]] = []

    # 1. Проверяем профили из info_cache
    for folder_name, info in info_cache.items():
        folder_path = user_data_dir / folder_name
        if not folder_path.exists() or not folder_path.is_dir():
            continue

        name = info.get("name", folder_name)
        user_name = info.get("user_name", "")
        has_cookies = (folder_path / "Network" / "Cookies").exists() or (folder_path / "Cookies").exists()

        profiles.append({
            "folder": folder_name,
            "name": name,
            "email": user_name,
            "has_cookies": has_cookies,
            "path": folder_path
        })

    # 2. Если какие-то папки не попали в info_cache
    known_folders = {p["folder"] for p in profiles}
    for sub in user_data_dir.iterdir():
        if sub.is_dir() and sub.name not in known_folders:
            if sub.name == "Default" or sub.name.startswith("Profile "):
                has_pref = (sub / "Preferences").exists()
                has_cookies = (sub / "Network" / "Cookies").exists() or (sub / "Cookies").exists()
                if has_pref or has_cookies:
                    profiles.append({
                        "folder": sub.name,
                        "name": sub.name,
                        "email": "",
                        "has_cookies": has_cookies,
                        "path": sub
                    })

    def sort_key(item: Dict[str, Any]) -> int:
        folder = item["folder"]
        if folder == "Default":
            return 0
        if folder.startswith("Profile "):
            try:
                return int(folder.split(" ", 1)[1])
            except ValueError:
                return 9999
        return 99999

    profiles.sort(key=sort_key)

    exhausted_map = get_exhausted_profiles()
    for p in profiles:
        folder = p["folder"]
        p["is_flow_ready"] = is_profile_flow_ready(folder)
        if folder in exhausted_map:
            p["is_exhausted"] = True
            p["cooldown_until"] = exhausted_map[folder].get("cooldown_until")
            p["exhausted_reason"] = exhausted_map[folder].get("reason", "")
        else:
            p["is_exhausted"] = False
            p["cooldown_until"] = None
            p["exhausted_reason"] = None

    return profiles

def resolve_profile_folder(
    selector: Optional[str] = None,
    user_data_dir: Optional[Path] = None,
    exclude: Optional[set[str]] = None,
) -> str:
    """
    Разрешает селектор профиля в имя реальной папки Chrome ('Default', 'Profile 2', и т.д.).
    Если указан 'auto', выбирает следующий профиль с учетом исключений и кулдаунов.
    """
    profiles = get_all_chrome_profiles(user_data_dir)
    if not profiles:
        return "Default"

    exclude_set = set(exclude or [])

    if selector is None or str(selector).strip() == "":
        for p in profiles:
            if p["folder"] == "Default" and p.get("is_flow_ready") and not p.get("is_exhausted") and p["folder"] not in exclude_set:
                return "Default"
        for p in profiles:
            if p.get("is_flow_ready") and not p.get("is_exhausted") and p["folder"] not in exclude_set:
                return p["folder"]
        for p in profiles:
            if p["has_cookies"] and not p.get("is_exhausted") and p["folder"] not in exclude_set:
                return p["folder"]
        for p in profiles:
            if p["folder"] not in exclude_set:
                return p["folder"]
        return profiles[0]["folder"]

    sel = str(selector).strip()

    if sel.lower() in ("auto", "rotate", "next"):
        return get_next_rotated_profile(profiles, exclude=exclude_set, user_data_dir=user_data_dir)

    # Точное совпадение с папкой
    for p in profiles:
        if p["folder"].lower() == sel.lower():
            return p["folder"]

    # Числовой ввод: 2 -> 'Profile 2'
    if sel.isdigit():
        target = f"Profile {sel}"
        for p in profiles:
            if p["folder"].lower() == target.lower():
                return p["folder"]
        idx = int(sel) - 1
        if 0 <= idx < len(profiles):
            return profiles[idx]["folder"]

    # Поиск по отображаемому имени в Chrome
    for p in profiles:
        if p["name"].lower() == sel.lower():
            return p["folder"]

    for p in profiles:
        if sel.lower() in p["name"].lower():
            return p["folder"]

    return sel

def get_next_rotated_profile(
    profiles: Optional[List[Dict[str, Any]]] = None,
    exclude: Optional[set[str]] = None,
    user_data_dir: Optional[Path] = None,
) -> str:
    """
    Round-robin ротация среди доступных профилей.
    Автоматически пропускает аккаунты, у которых исчерпан лимит (кулдаун), которые переданы в exclude,
    или которые еще не имеют активной сессии Google Flow.
    """
    if profiles is None:
        profiles = get_all_chrome_profiles(user_data_dir)

    if not profiles:
        return "Default"

    exclude_set = set(exclude or [])
    exhausted_map = get_exhausted_profiles()
    all_exhausted = set(exhausted_map.keys())

    # 1. Высший приоритет: профили с ПОЛНОСТЬЮ авторизованной сессией Flow (is_flow_ready), не исчерпанные и не в exclude
    candidates = [
        p["folder"] for p in profiles 
        if p.get("is_flow_ready") and p["folder"] not in exclude_set and p["folder"] not in all_exhausted
    ]

    # 2. Если все авторизованные профили в exclude (например, в рамках одной попытки), но есть другие авторизованные
    if not candidates and not [p for p in profiles if p.get("is_flow_ready")]:
        # Только если НЕТ ни одного с flow сессией, пробуем другие профили с куками
        candidates = [
            p["folder"] for p in profiles 
            if p.get("has_cookies") and p["folder"] not in exclude_set and p["folder"] not in all_exhausted
        ]

    # 3. Если все кандидаты исключены
    if not candidates:
        ready = [p["folder"] for p in profiles if p.get("is_flow_ready") and p["folder"] not in exclude_set]
        if ready:
            return ready[0]
        ready_any = [p["folder"] for p in profiles if p.get("is_flow_ready")]
        if ready_any:
            return ready_any[0]
        return "Default"

    last_index = -1
    if ROTATION_STATE_FILE.exists():
        try:
            data = json.loads(ROTATION_STATE_FILE.read_text(encoding="utf-8"))
            last_profile = data.get("last_profile", "")
            if last_profile in candidates:
                last_index = candidates.index(last_profile)
        except Exception:
            pass

    next_index = (last_index + 1) % len(candidates)
    chosen_profile = candidates[next_index]

    try:
        ROTATION_STATE_FILE.write_text(
            json.dumps({"last_profile": chosen_profile, "updated_at": time.time()}),
            encoding="utf-8"
        )
    except Exception:
        pass

    return chosen_profile

def sync_chrome_profile_for_automation(
    profile_folder: str,
    user_data_dir: Optional[Path] = None,
    force_sync: bool = False
) -> Path:
    """
    Создает изолированный снимок сессии для Playwright, предотвращая ошибку ProcessSingleton.
    """
    if user_data_dir is None:
        user_data_dir = get_chrome_user_data_path()

    src_profile = user_data_dir / profile_folder
    if not src_profile.exists():
        if profile_folder == "Default":
            src_profile = user_data_dir / "Default"

    dest_dir = CACHE_PROFILES_DIR / profile_folder.replace(" ", "_")
    dest_profile = dest_dir / "Default"
    dest_profile.mkdir(parents=True, exist_ok=True)

    # Если профиль автоматизации уже инициализирован, не перезаписываем его файлы
    if (dest_profile / "Preferences").exists() and not force_sync:
        return dest_dir

    # Копируем только базовые настройки Preferences без блокировки баз данных
    src_pref = src_profile / "Preferences"
    dest_pref = dest_profile / "Preferences"
    if src_pref.exists() and not dest_pref.exists():
        try:
            shutil.copy2(src_pref, dest_pref)
        except Exception:
            pass

    return dest_dir

def mask_email(email: str) -> str:
    """Маскирует email для безопасного отображения без утечки данных."""
    if not email or "@" not in email:
        return email
    parts = email.split("@", 1)
    username = parts[0]
    domain = parts[1]
    if len(username) <= 3:
        masked_user = username[0] + "***"
    else:
        masked_user = username[:2] + "***" + username[-1]
    return f"{masked_user}@{domain}"

SESSIONS_DIR = BASE_DIR / ".flow_sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

def find_chrome_executable() -> Optional[Path]:
    """Ищет путь к исполняемому файлу Google Chrome на Windows."""
    candidates = [
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None

def verify_session(profile_folder: str) -> tuple[bool, Optional[str]]:
    """Быстрая проверка сессии Google Flow через NextAuth session API."""
    session_file = get_session_file(profile_folder)
    if not session_file.exists():
        return False, None
    try:
        data = json.loads(session_file.read_text(encoding="utf-8"))
        cookies = {c["name"]: c["value"] for c in data.get("cookies", [])}
        if not cookies or "__Secure-next-auth.session-token" not in cookies:
            return False, None
        import urllib.request
        req = urllib.request.Request("https://labs.google/fx/api/auth/session")
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        req.add_header("Cookie", cookie_str)
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp_data = json.loads(resp.read().decode())
            if resp_data and resp_data.get("user"):
                return True, resp_data.get("user", {}).get("email")
            return False, None
    except Exception:
        return False, None

