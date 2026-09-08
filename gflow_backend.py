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
    """Приводит варианты ввода (10, 'Profile 10', 'p10', '#10') к каноническому имени профиля gflow."""
    if not selector:
        return "auto"
    s = str(selector).strip()
    if s.lower() in ("auto", "rotate", "next"):
        return "auto"
    m = re.match(r"^(?:profile\s*|p|#)(\d+)$", s, re.IGNORECASE)
    if m:
        return m.group(1)
    if s.lower() == "default":
        return "default"
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

def login(profile: str) -> bool:
    """Запускает авторизацию указанного профиля через gflow auth login с настоящим Chrome."""
    clean_name = normalize_profile_name(profile)
    if clean_name == "auto":
        clean_name = "default"

    cmd = [get_gflow_bin(), "auth", "login", "--profile", clean_name, "--browser", "chrome"]
    print(f"\n" + "=" * 80)
    print(f" 🚀 АВТОРИЗАЦИЯ GFLOW: ПРОФИЛЬ '{clean_name}'")
    print("=" * 80)
    print(" 💡 Сейчас откроется чистое окно Google Chrome.")
    print(" 👉 Войдите в ваш Google аккаунт на странице Flow и после завершения закройте окно Chrome.")
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
            print(f" [✔] ПРОФИЛЬ '{clean_name}' УСПЕШНО АВТОРИЗОВАН!")
            if email:
                print(f"     Google Email : {email}")
            print("     Сессия надежно сохранена в SQLite базе данных gflow.")
            print(f"     Команда запуска: .\\generate.bat {clean_name} \"Ваш промпт\"")
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
