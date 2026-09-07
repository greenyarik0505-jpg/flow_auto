"""
Web2API HTTP-сервер для Google Flow (Gemini Omni / Veo / Imagen 4)
Позволяет отправлять промпты через REST API, отслеживать статус и скачивать готовые видео и фото.
"""
import os
import sys
import uuid
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, Literal
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import chrome_profiles

BASE_DIR = Path(__file__).parent.resolve()
VENV_GFLOW = BASE_DIR / ".venv" / "Scripts" / "gflow.exe"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def get_gflow_bin() -> str:
    if VENV_GFLOW.exists():
        return str(VENV_GFLOW)
    return "gflow"

app = FastAPI(
    title="Google Flow Web2API (Gemini Omni / Veo / Imagen)",
    description="""
## REST API для генерации видео и изображений через Google Flow

* **Генерация видео**:
  * Модели: `omni-flash` (Gemini Omni — быстро, до 10 сек.), `veo-quality` (Veo 3.1 — кинокачество), `veo-fast`, `veo-lite`.
  * Форматы: 16:9 (горизонтальное), 9:16 (вертикальное для Shorts / Reels / TikTok).
* **Генерация фото**:
  * Модели: `nano-pro` (Nano Banana Pro — детализированное), `image4` (Imagen 4 — фотореализм), `nano2` (сверхбыстрое).
  * Форматы: 16:9, 9:16, 1:1 (квадратное), 4:3, 3:4.
  * Количество: от 1 до 4 вариантов за один запрос.
* **Мультиаккаунты (40+ профилей)**:
  * Поддержка выбора профиля Chrome (`profile`: "Default", "2", "Profile 2", "auto").
    """,
    version="1.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Хранилище задач в памяти
tasks: dict[str, dict] = {}

class GenerateVideoRequest(BaseModel):
    prompt: str = Field(
        ...,
        description="Текстовое описание сцены (промпт)",
        examples=["A futuristic flying car over neon cyberpunk city at night, rain reflections, 4k cinematic"]
    )
    model: Literal["omni-flash", "veo-quality", "veo-fast", "veo-lite", "veo-lite-lp"] = Field(
        default="omni-flash",
        description="Модель генерации видео. По умолчанию omni-flash (Gemini Omni)"
    )
    aspect: Literal["16:9", "9:16"] = Field(
        default="16:9",
        description="Соотношение сторон: 16:9 (горизонтальное) или 9:16 (вертикальное)"
    )
    duration: Optional[Literal[4, 6, 8, 10]] = Field(
        default=None,
        description="Длительность клипа в секундах (omni-flash поддерживает 4, 6, 8, 10)"
    )
    profile: Optional[str] = Field(
        default=None,
        description="Профиль Chrome (например: 2, 'Profile 2', 'GeminiPro' или 'auto' для ротации 40 аккаунтов)"
    )
    wait: bool = Field(
        default=False,
        description="Если True — запрос подождет окончания рендера и вернет видео сразу. Если False — вернет task_id для опроса."
    )

class GenerateImageRequest(BaseModel):
    prompt: str = Field(
        ...,
        description="Текстовое описание изображения (промпт)",
        examples=["Hyperrealistic macro photography of a crystal butterfly on a luminous neon flower"]
    )
    model: Literal["nano-pro", "nano2", "image4", "imagen4"] = Field(
        default="nano-pro",
        description="Модель генерации фото: nano-pro (высокое качество), image4 (Imagen 4), nano2 (быстрое)"
    )
    aspect: Literal["16:9", "9:16", "1:1", "4:3", "3:4"] = Field(
        default="16:9",
        description="Соотношение сторон: 16:9, 9:16, 1:1, 4:3, 3:4"
    )
    count: int = Field(
        default=1,
        ge=1,
        le=4,
        description="Количество генерируемых картинок (от 1 до 4)"
    )
    profile: Optional[str] = Field(
        default=None,
        description="Профиль Chrome (например: 2, 'Profile 2', 'GeminiPro' или 'auto' для ротации 40 аккаунтов)"
    )
    wait: bool = Field(
        default=True,
        description="Если True — запрос подождет генерации (~15 сек.) и сразу вернет список ссылок на фото."
    )

def check_gflow_auth() -> dict:
    profiles = chrome_profiles.get_all_chrome_profiles()
    active_chrome = [p for p in profiles if p["has_cookies"]]
    if active_chrome:
        return {
            "authenticated": True,
            "method": "chrome_profiles",
            "profiles_count": len(profiles),
            "active_count": len(active_chrome),
            "detail": f"Обнаружено {len(active_chrome)} активных профилей Chrome с готовой сессией."
        }

    cmd = [get_gflow_bin(), "auth", "status"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    is_authenticated = proc.returncode == 0
    return {
        "authenticated": is_authenticated,
        "method": "gflow",
        "detail": proc.stdout.strip() if is_authenticated else (proc.stderr.strip() or proc.stdout.strip() or "Не авторизовано")
    }

async def run_video_task(task_id: str, req: GenerateVideoRequest):
    task = tasks[task_id]
    task["status"] = "running"
    task["started_at"] = datetime.now().isoformat()

    task_out_dir = OUTPUT_DIR / "videos" / task_id
    task_out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(BASE_DIR / "generate_video.py"),
        req.prompt,
        "--model", req.model,
        "--aspect", req.aspect,
        "--out-dir", str(task_out_dir),
    ]

    if req.duration:
        cmd.extend(["--duration", str(req.duration)])
    if req.profile:
        cmd.extend(["--profile", str(req.profile)])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )

        stdout_data, _ = await proc.communicate()
        raw_output = stdout_data.decode("utf-8", errors="replace")
        task["logs"] = raw_output

        if proc.returncode == 0:
            mp4_files = list(task_out_dir.rglob("*.mp4"))
            if mp4_files:
                video_file = mp4_files[0]
                task["status"] = "completed"
                task["video_path"] = str(video_file)
                task["video_filename"] = video_file.name
                task["download_url"] = f"/api/v1/videos/{task_id}/{video_file.name}"
            else:
                task["status"] = "completed"
                task["video_path"] = None
                task["download_url"] = None
                task["note"] = "Генерация завершена, но .mp4 не найден"
        else:
            task["status"] = "failed"
            task["error"] = f"Процесс генерации завершился с кодом {proc.returncode}"

    except Exception as e:
        task["status"] = "failed"
        task["error"] = str(e)
    finally:
        task["finished_at"] = datetime.now().isoformat()

async def run_image_task(task_id: str, req: GenerateImageRequest):
    task = tasks[task_id]
    task["status"] = "running"
    task["started_at"] = datetime.now().isoformat()

    task_out_dir = OUTPUT_DIR / "images" / task_id
    task_out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(BASE_DIR / "generate_image.py"),
        req.prompt,
        "--model", req.model,
        "--aspect", req.aspect,
        "-n", str(req.count),
        "--out-dir", str(task_out_dir),
    ]
    if req.profile:
        cmd.extend(["--profile", str(req.profile)])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )

        stdout_data, _ = await proc.communicate()
        raw_output = stdout_data.decode("utf-8", errors="replace")
        task["logs"] = raw_output

        if proc.returncode == 0:
            png_files = sorted(list(task_out_dir.glob("*.png")))
            if png_files:
                task["status"] = "completed"
                task["images"] = [
                    {
                        "filename": f.name,
                        "path": str(f),
                        "download_url": f"/api/v1/images/{task_id}/{f.name}"
                    }
                    for f in png_files
                ]
            else:
                task["status"] = "completed"
                task["images"] = []
                task["note"] = "Генерация завершена, но файлы .png не найдены"
        else:
            task["status"] = "failed"
            task["error"] = f"Процесс генерации завершился с кодом {proc.returncode}"

    except Exception as e:
        task["status"] = "failed"
        task["error"] = str(e)
    finally:
        task["finished_at"] = datetime.now().isoformat()

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

@app.get("/", tags=["Информация"])
def index():
    return {
        "service": "Google Flow Web2API",
        "status": "online",
        "docs": "/docs",
        "models": {
            "default_video": "omni-flash (Gemini Omni)",
            "default_image": "nano-pro (Nano Banana Pro / Imagen)"
        }
    }

@app.get("/api/v1/auth/status", tags=["Статус и Авторизация"])
def get_auth_status():
    """Проверка текущего статуса авторизации в Google Flow"""
    return check_gflow_auth()

@app.get("/api/v1/profiles", tags=["Профили Chrome"])
def get_profiles_list():
    """
    Возвращает список всех профилей Google Chrome в системе (поддержка 40+ аккаунтов).
    Каждый профиль можно использовать для генерации, передав его имя в поле 'profile'.
    """
    profiles = chrome_profiles.get_all_chrome_profiles()
    return {
        "count": len(profiles),
        "ready_count": sum(1 for p in profiles if p["has_cookies"]),
        "profiles": [
            {
                "folder": p["folder"],
                "name": p["name"],
                "masked_email": chrome_profiles.mask_email(p["email"]),
                "ready": p["has_cookies"]
            }
            for p in profiles
        ]
    }

@app.get("/api/v1/models", tags=["Статус и Авторизация"])
def list_models():
    """Список поддерживаемых моделей Google Flow для видео и фото"""
    return {
        "video_models": [
            {
                "id": "omni-flash",
                "name": "Gemini Omni (Omni Flash)",
                "description": "Сверхбыстрая модель нового поколения, длительность клипа от 4 до 10 сек.",
                "durations": [4, 6, 8, 10],
                "default": True
            },
            {
                "id": "veo-quality",
                "name": "Veo 3.1 Quality",
                "description": "Максимальное кинематографическое качество",
                "durations": [4, 6, 8],
                "default": False
            },
            {
                "id": "veo-fast",
                "name": "Veo 3.1 Fast",
                "description": "Быстрый рендеринг Veo",
                "durations": [4, 6, 8],
                "default": False
            },
            {
                "id": "veo-lite",
                "name": "Veo 3.1 Lite",
                "description": "Облегченная модель",
                "durations": [4, 6, 8],
                "default": False
            }
        ],
        "image_models": [
            {
                "id": "nano-pro",
                "name": "Nano Banana Pro (GEM_PIX_2)",
                "description": "Высокая детализация и качество",
                "default": True
            },
            {
                "id": "image4",
                "name": "Imagen 4 (IMAGEN_3_5)",
                "description": "Фотореалистичный рендеринг сцен и объектов",
                "default": False
            },
            {
                "id": "nano2",
                "name": "Nano Banana 2 (NARWHAL)",
                "description": "Сверхбыстрая генерация картинок",
                "default": False
            }
        ]
    }

@app.post("/api/v1/generate", tags=["Генерация видео"])
async def create_video_generation(req: GenerateVideoRequest, background_tasks: BackgroundTasks):
    """
    Отправить промпт на генерацию видео в Google Flow (Gemini Omni / Veo).
    * Если **wait=True** — запрос ждет окончания рендера (~1-2 мин) и вернет видео сразу.
    * Если **wait=False** — сразу вернет **task_id** для проверки через `GET /api/v1/tasks/{task_id}`.
    """
    auth = check_gflow_auth()
    if not auth["authenticated"]:
        raise HTTPException(
            status_code=401,
            detail="Google Flow не авторизован. Запустите '.\\login.bat' в терминале для входа."
        )

    task_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {
        "task_id": task_id,
        "type": "video",
        "prompt": req.prompt,
        "model": req.model,
        "aspect": req.aspect,
        "duration": req.duration,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "video_path": None,
        "download_url": None,
        "logs": "",
        "error": None
    }

    if req.wait:
        await run_video_task(task_id, req)
        return tasks[task_id]
    else:
        background_tasks.add_task(run_video_task, task_id, req)
        return {
            "task_id": task_id,
            "status": "queued",
            "message": "Генерация видео запущена в фоновом режиме",
            "check_status_url": f"/api/v1/tasks/{task_id}"
        }

@app.post("/api/v1/generate-image", tags=["Генерация изображений"])
async def create_image_generation(req: GenerateImageRequest, background_tasks: BackgroundTasks):
    """
    Отправить промпт на генерацию изображений через Google Flow (Imagen 4 / Nano Banana).
    * По умолчанию **wait=True** — генерация занимает всего ~10-25 секунд и сразу возвращает готовые картинки!
    * Поддерживается от 1 до 4 картинок (`count`), форматы 16:9, 9:16, 1:1, 4:3, 3:4.
    """
    auth = check_gflow_auth()
    if not auth["authenticated"]:
        raise HTTPException(
            status_code=401,
            detail="Google Flow не авторизован. Запустите '.\\login.bat' в терминале для входа."
        )

    task_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {
        "task_id": task_id,
        "type": "image",
        "prompt": req.prompt,
        "model": req.model,
        "aspect": req.aspect,
        "count": req.count,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "images": [],
        "logs": "",
        "error": None
    }

    if req.wait:
        await run_image_task(task_id, req)
        return tasks[task_id]
    else:
        background_tasks.add_task(run_image_task, task_id, req)
        return {
            "task_id": task_id,
            "status": "queued",
            "message": "Генерация фото запущена в фоновом режиме",
            "check_status_url": f"/api/v1/tasks/{task_id}"
        }

@app.get("/api/v1/tasks", tags=["Задачи и Готовые файлы"])
def list_tasks():
    """Получить список всех запущенных и завершенных задач (видео и фото)"""
    return list(tasks.values())

@app.get("/api/v1/tasks/{task_id}", tags=["Задачи и Готовые файлы"])
def get_task(task_id: str):
    """Получить статус, логи и ссылки на скачивание для конкретной задачи"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return tasks[task_id]

@app.get("/api/v1/videos/{task_id}/{filename}", tags=["Задачи и Готовые файлы"])
def download_video(task_id: str, filename: str):
    """Скачать сгенерированный видеофайл .mp4"""
    file_path = OUTPUT_DIR / "videos" / task_id / filename
    if not file_path.exists():
        # Fallback для старых путей без подпапки videos
        fallback = OUTPUT_DIR / task_id / filename
        if fallback.exists():
            return FileResponse(fallback, media_type="video/mp4", filename=filename)
        raise HTTPException(status_code=404, detail="Видеофайл не найден")
    return FileResponse(file_path, media_type="video/mp4", filename=filename)

@app.get("/api/v1/images/{task_id}/{filename}", tags=["Задачи и Готовые файлы"])
def download_image(task_id: str, filename: str):
    """Скачать сгенерированное изображение .png"""
    file_path = OUTPUT_DIR / "images" / task_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Файл изображения не найден")
    return FileResponse(file_path, media_type="image/png", filename=filename)

if __name__ == "__main__":
    import uvicorn
    print("\n[+] Web2API сервер Google Flow готов к работе:")
    print("    Главная страница:      http://127.0.0.1:8000")
    print("    Swagger документация:  http://127.0.0.1:8000/docs\n")
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
