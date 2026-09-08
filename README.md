# 🎬 Google Flow Web2API & CLI (Gemini Omni / Veo / Imagen 4)

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Playwright](https://img.shields.io/badge/Playwright-Chromium-green.svg)](https://playwright.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Google Flow](https://img.shields.io/badge/Google%20Flow-Veo%20%7C%20Gemini%20Omni%20%7C%20Imagen-red.svg)](https://labs.google/fx/tools/flow)

Автоматизированный инструмент и локальный **REST Web2API сервер** для генерации видео и изображений через студию **Google Flow** ([flow.google.com](http://flow.google.com/?pli=1) / [labs.google/fx/tools/flow](https://labs.google/fx/tools/flow)).

Поддерживает передовые генеративные модели Google:
* **Видео**: **Gemini Omni** (`omni-flash` — длительность клипов до 10 сек.), **Veo 3.1 Quality**, **Veo 3.1 Fast**, **Veo 3.1 Lite**.
* **Фото**: **Imagen 4** (`image4`), **Nano Banana Pro** (`nano-pro` — высокая детализация), **Nano Banana 2** (`nano2` — быстрый рендер).

---

## 📑 Содержание
1. [Возможности](#-возможности)
2. [Архитектура решения](#-архитектура-решения)
3. [Быстрый старт и Авторизация](#-быстрый-старт)
4. [Генерация Видео через Терминал (CLI)](#-1-генерация-видео-через-терминал-cli)
5. [Генерация Фото через Терминал (CLI)](#-2-генерация-фото-через-терминал-cli)
6. [Web2API (REST API & Swagger UI)](#-3-web2api-rest-api--swagger-ui)
7. [Примеры интеграции (Python / cURL / Telegram Bot)](#-4-примеры-интеграции)
8. [Таблица поддерживаемых моделей](#-5-таблица-моделей-и-форматов)
9. [Структура проекта](#-6-структура-проекта)
10. [Частые вопросы и Решение проблем](#-7-частые-вопросы-и-faq)

---

## ✨ Возможности

- 🚀 **Работа через одну команду в терминале**: отдайте текстовый промпт — получите готовый файл `.mp4` или `.png`.
- 🌐 **Полноценный REST API**: локальный HTTP-сервер на FastAPI с поддержкой синхронного ожидания (`wait=true`) или асинхронной очереди задач (`task_id`).
- 📖 **Интерактивная Swagger UI документация**: доступна по адресу `http://localhost:8000/docs` на чистом русском языке.
- 🔐 **Безопасная пассивная авторизация**: реальный профиль Google Chrome с долгоживущей сессией (не требует постоянного ввода логинов и SMS-кодов).
- 🎬 **Полный контроль параметров**: поддержка соотношений сторон `16:9`, `9:16` (Shorts/Reels), `1:1`, `4:3`, `3:4`, длительности клипов до 10 секунд и пакетной генерации до 4 вариантов.
- ⚡ **Полная русификация**: интерфейсы консоли, сообщения о статусе и сайт Flow открываются на русском языке.

---

## 🏗 Архитектура решения

```
┌────────────────────────────────────────────────────────┐
│               Ваш скрипт / Бот / Терминал              │
└──────────────────────────┬─────────────────────────────┘
                           │
            ┌──────────────┴──────────────┐
            ▼                             ▼
    [ generate.bat / CLI ]        [ server.py / REST API ]
            │                             │
            └──────────────┬──────────────┘
                           ▼
          flow_engine.py (Direct Automation)
                           │
                           ▼
            Playwright Chromium (Headless)
                           │
                           ▼
         Google Flow (flow.google.com / Veo / Omni)
            ├── Gemini Omni / Veo 3.1 ──► ./output/videos/*.mp4
            └── Imagen 4 / Nano Banana ──► ./output/images/*.png
```

---

## 🚀 Быстрый старт

Виртуальное окружение `.venv` со всеми зависимостями и Playwright Chromium уже настроено в проекте.

### Шаг 1. Разовая авторизация в Google Flow

Google защищает студию Flow через OAuth и reCAPTCHA Enterprise. Авторизация требуется **ровно один раз**:

Запустите:
```powershell
.\login.bat
```

## 👥 Мультиаккаунтинг (40+ профилей Chrome)

Если у вас настроено **40 аккаунтов в Google Chrome**, генератор может работать со всеми ними полностью в фоне!

### 1. Просмотр всех профилей Chrome в вашей системе:
```powershell
.\list_profiles.bat
```
Скрипт автоматически просканирует Google Chrome и выведет список всех доступных профилей с их номерами, именами и статусом готовности.

### 2. Автоматический захват сессий по очереди (для всех 40 профилей):
Запустите привязку всех аккаунтов одной командой:
```powershell
.\login.bat --all
```
* Скрипт по очереди открывает каждый ваш профиль в настоящем Google Chrome (со всеми сохраненными аккаунтами, **без режима гостя**!).
* Никаких расширений устанавливать не нужно!
* Как только вы попадаете в Google Flow под этим аккаунтом:
  - **Автоматически:** скрипт напрямую считывает токен сессии из памяти Chrome за ~1 секунду!
  - **Автопроверка:** скрипт проверяет валидность токена через официальный API Google (`labs.google/fx/api/auth/session`).
  - **Мгновенный переход:** сразу сохраняет сессию в `.flow_sessions/` и переходит к следующему профилю!
* Для одного конкретного профиля:
  ```powershell
  .\login.bat 2
  ```
* Либо прямая передача токена в 1 строку:
  ```powershell
  .\login.bat 2 "значение_токена"
  ```

### 3. Выбор профиля при генерации:
* **По номеру профиля:**
  ```powershell
  .\generate.bat "A futuristic supercar" --profile 2
  ```
* **По названию профиля в Chrome:**
  ```powershell
  .\generate.bat "Cyberpunk neon city" --profile "GeminiPro"
  ```
* **Автоматическая ротация и мгновенный обход лимитов (--profile auto):**
  ```powershell
  .\generate.bat "Cinematic nature drone shot" --profile auto
  ```
  *(Система распределяет генерации между всеми профилями. **Если на текущем аккаунте закончились кредиты (`0 credits`) или сработал лимит Google Flow, генератор мгновенно переходит на следующий рабочий аккаунт и повторяет генерацию без остановки!**)*
* **Сброс таймеров исчерпанных лимитов:**
  ```powershell
  .\generate.bat --reset-limits
  ```
  *(Сбрасывает 12-часовые кулдауны для всех профилей, возвращая их в пул активных).*

---

## 🎥 1. Генерация Видео через Терминал (CLI)

### Простой запуск:
```powershell
.\generate.bat "A futuristic flying car over neon cyberpunk city at night, rain reflections, 4k cinematic" --profile auto
```

### Запуск через Python с гибкими настройками:
```powershell
.\.venv\Scripts\python.exe generate_video.py "Cinematic drone shot of sunset over mountain peaks" --model omni-flash --aspect 16:9 --duration 8 --profile auto
```

### Доступные флаги:
| Флаг | Значения | Описание |
|---|---|---|
| `prompt` | Текст | Описание сцены для генерации |
| `--model` | `omni-flash`, `veo-quality`, `veo-fast`, `veo-lite` | Модель видео. По умолчанию `omni-flash` (Gemini Omni) |
| `--aspect` | `16:9`, `9:16` | Формат кадра: горизонтальный или вертикальный |
| `--duration` | `4`, `6`, `8`, `10` | Длительность клипа в секундах (`omni-flash` поддерживает до 10 сек.) |
| `--out-dir` | Путь к папке | Каталог для сохранения (по умолчанию `./output/videos`) |
| `--profile` | `auto`, `2`, `"Profile 2"` | Профиль Chrome. При `auto` автоматически переключается при исчерпании лимитов |
| `--list-profiles` | Флаг | Показать таблицу всех профилей Chrome в системе |
| `--reset-limits` | Флаг | Сбросить кэш исчерпанных квот/лимитов для всех профилей |

Готовые файлы `.mp4` автоматически сохраняются в папку `./output/videos`.

---

## 🖼 2. Генерация Фото через Терминал (CLI)

Генерация изображений в Google Flow работает через модель **Imagen 4** и занимает всего **10–20 секунд** (и не расходует кредиты Veo!).

### Простой запуск:
```powershell
.\generate_image.bat "A cute red panda wearing a tiny astronaut suit on Mars, highly detailed, photorealistic" --profile auto
```

### Запуск через Python с параметрами:
```powershell
.\.venv\Scripts\python.exe generate_image.py "Cyberpunk neon street ramen shop in rain" --model image4 --aspect 16:9 -n 2 --profile auto
```

### Доступные флаги:
| Флаг | Значения | Описание |
|---|---|---|
| `prompt` | Текст | Описание изображения |
| `--model` | `nano-pro`, `image4`, `nano2` | `nano-pro` (высокая детализация), `image4` (Imagen 4), `nano2` (сверхбыстрый) |
| `--aspect` | `16:9`, `9:16`, `1:1`, `4:3`, `3:4` | Соотношение сторон фото |
| `-n`, `--count` | `1`, `2`, `3`, `4` | Количество генерируемых вариантов |
| `--out-dir` | Путь к папке | Папка сохранения (по умолчанию `./output/images`) |
| `--profile` | `auto`, `2`, `"Profile 2"` | Профиль Chrome. При `auto` автоматически переключается при исчерпании лимитов |
| `--list-profiles` | Флаг | Показать таблицу всех профилей Chrome в системе |
| `--reset-limits` | Флаг | Сбросить кэш исчерпанных квот/лимитов для всех профилей |

---

## 🌐 3. Web2API (REST API & Swagger UI)

### Запуск сервера:
```powershell
.\start_server.bat
```
*(или: `.\.venv\Scripts\python.exe server.py`)*

* **Адрес API:** `http://localhost:8000`
* **Интерактивная панель Swagger:** 👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**

---

### Основные эндпоинты:

#### 1. Генерация видео
`POST /api/v1/generate`

**Тело запроса (JSON):**
```json
{
  "prompt": "Macro shot of a glowing butterfly on a crystal flower in enchanted forest",
  "model": "omni-flash",
  "aspect": "16:9",
  "duration": 8,
  "wait": true
}
```
* Если `"wait": true` — сервер заблокирует запрос на время рендера (~1–2 мин) и сразу вернет ссылку на готовый `.mp4`.
* Если `"wait": false` — сервер моментально вернет `{"task_id": "...", "status": "queued"}`, статус которого можно опрашивать.

#### 2. Генерация фото
`POST /api/v1/generate-image`

**Тело запроса (JSON):**
```json
{
  "prompt": "Futuristic sport car in neon garage, reflections, ray tracing 8k",
  "model": "nano-pro",
  "aspect": "16:9",
  "count": 2,
  "wait": true
}
```

#### 3. Проверка статуса задачи
`GET /api/v1/tasks/{task_id}`

Ответ:
```json
{
  "task_id": "c7a8b9f1",
  "status": "completed",
  "prompt": "...",
  "download_url": "/api/v1/videos/c7a8b9f1/video_0.mp4"
}
```

#### 4. Скачивание готового файла
- Видео: `GET /api/v1/videos/{task_id}/{filename}`
- Фото: `GET /api/v1/images/{task_id}/{filename}`

---

## 💻 4. Примеры интеграции

### Python (библиотека `httpx` или `requests`):
```python
import httpx
import time

API_URL = "http://localhost:8000"

# 1. Отправляем запрос на генерацию
resp = httpx.post(f"{API_URL}/api/v1/generate", json={
    "prompt": "Golden retriever puppy running in green field at sunset",
    "model": "omni-flash",
    "aspect": "16:9",
    "duration": 8,
    "wait": False
})
task_id = resp.json()["task_id"]
print(f"Задача запущена: {task_id}")

# 2. Ожидаем готовности
while True:
    task = httpx.get(f"{API_URL}/api/v1/tasks/{task_id}").json()
    if task["status"] == "completed":
        print(f"Готово! Скачать: {API_URL}{task['download_url']}")
        break
    elif task["status"] == "failed":
        print("Ошибка генерации:", task["error"])
        break
    time.sleep(5)
```

### cURL (Linux / macOS / Windows):
```bash
curl -X POST "http://localhost:8000/api/v1/generate" \
     -H "Content-Type: application/json" \
     -d '{
       "prompt": "A majestic eagle soaring over snowy mountains, 4k cinematic",
       "model": "omni-flash",
       "aspect": "16:9",
       "duration": 8,
       "wait": true
     }'
```

---

## 📊 5. Таблица моделей и форматов

### Модели Видео (Google Veo & Gemini Omni):
| Имя модели | Описание | Поддерживаемая длительность |
|---|---|---|
| `omni-flash` | **Gemini Omni** — самая современная и быстрая модель | 4с, 6с, 8с, 10с |
| `veo-quality` | **Veo 3.1 Quality** — максимальная кинематографичность | 4с, 6с, 8с |
| `veo-fast` | **Veo 3.1 Fast** — ускоренный рендеринг | 4с, 6с, 8с |
| `veo-lite` | **Veo 3.1 Lite** — облегченная версия | 4с, 6с, 8с |

### Модели Фото (Google Imagen):
| Имя модели | Описание | Форматы |
|---|---|---|
| `nano-pro` | **Nano Banana Pro** — детализация и мелкие элементы | 16:9, 9:16, 1:1, 4:3, 3:4 |
| `image4` | **Imagen 4** — фотореализм и текстуры | 16:9, 9:16, 1:1, 4:3, 3:4 |
| `nano2` | **Nano Banana 2** — быстрый концепт-арт | 16:9, 9:16, 1:1, 4:3, 3:4 |

---

## 📁 6. Структура проекта

```
flow_auto/
├── .venv/                  # Изолированное окружение Python и Playwright
├── output/                 # Папка с сгенерированными видео и фото
│   ├── videos/             # Готовые .mp4 клипы
│   └── images/             # Готовые .png фото
├── flow_engine.py          # Автономный движок генерации и скачивания (Playwright)
├── chrome_profiles.py      # Модуль обнаружения и ротации 40+ профилей Chrome
├── list_profiles.bat       # Просмотр всех профилей Chrome в терминале
├── flow_extension/         # 1-клик расширение Chrome для копирования токена Flow
├── login.bat               # Батник быстрой привязки и проверки профилей Chrome
├── login.py                # Скрипт сохранения сессий и аккаунтов Chrome
├── generate.bat            # Быстрый запуск генерации видео из терминала
├── generate_video.py       # Основной скрипт генератора видео
├── generate_image.bat      # Быстрый запуск генерации фото из терминала
├── generate_image.py       # Основной скрипт генератора фото
├── start_server.bat        # Запуск Web2API REST-сервера
├── server.py               # Сервер FastAPI со Swagger документацией
├── requirements.txt        # Список зависимостей Python
└── README.md               # Полная документация проекта
```

---

## ❓ 7. Частые вопросы и FAQ

**В: Сгорают ли кредиты при ошибках?**
О: Нет. Кредиты Google Flow списываются только за успешную генерацию видео моделью Veo. Генерация изображений Imagen бесплатна.

**В: Как часто нужно логиниться через `login.bat`?**
О: Один раз в несколько недель. Сессия Google Flow сохраняется в локальный профиль браузера и автоматически используется при каждом последующем запросе.

**В: Можно ли использовать сервис одновременно с открытым Chrome?**
О: Да! Автоматизация использует отдельный профиль `profile_default`, поэтому ваш основной Google Chrome может быть открыт и использоваться параллельно для работы или серфинга.
