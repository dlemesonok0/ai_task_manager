# Инструкции для агентов

## Язык

Проектные документы, рабочие заметки, описания задач, roadmap, backlog и итоговые отчеты — на русском.
Код, имена переменных, API-поля, команды, статусы задач и технические идентификаторы — на английском.

## Ветки

Любая feature, fix или нетривиальная правка — в отдельной ветке. Не коммитить напрямую в `master`.

## Структура проекта

- `backend/` — Python 3.13, FastAPI + aiogram Telegram bot
- `frontend/` — React + Vite + TypeScript (вся логика в одном `App.tsx`)
- `docs/tasks/` — текущие/бэклог/выполненные задачи

## Команды

**Backend** (требуется `uv`):
- `uv sync` — установка зависимостей
- `uv run pytest` — все тесты (pytest-asyncio, coverage)
- `uv run uvicorn main:app --reload` — API на `:8000`
- `uv run python bot.py` — Telegram bot (отдельный терминал)

**Frontend**:
- `npm install` — установка зависимостей
- `npm run dev` — dev-сервер на `:5173`
- `npm test` — vitest run (jsdom, coverage v8)
- `npm run build` — `tsc && vite build`
- `npm run lint` — eslint, `--max-warnings 0`

## Особенности

- **База**: PostgreSQL через docker-compose на порту 15432. Таблицы создаются в `init_db()` при старте FastAPI.
- **Аутентификация**: кастомный JWT (HMAC). Dev-креды: `admin`/`admin`.
- **AI-сервис** (`backend/services/ai_service.py`): провайдер определяется по env-переменным (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `LLM_BASE_URL`). Для парсинга задач из текста (Telegram).
- **Переменные окружения**: все в `backend/.env`, пример в `.env.example`. Токены (Todoist, Google, Telegram) — персональные, хранятся в БД для каждого пользователя.
- **Docker**: образы публикуются в GHCR, деплой на сервер через SSH после мержа в master (CI).

## Тестирование

**Backend**:
- `conftest.py` подменяет `db_service` на `FakeDatabase` через `monkeypatch` — тесты не требуют реальной БД.
- Todoist/Google Calendar сервисы мокаются через `AsyncMock`/`MagicMock`.
- Асинхронные тесты: `@pytest.mark.asyncio` (asyncio_mode = auto в pyproject.toml).

**Frontend**:
- `vitest` с `jsdom`, `@testing-library/react`.
- Паттерн: глобальный `vi.stubGlobal('fetch', ...)` в каждом тесте.
- Токен хранится в `localStorage` под ключом `ai-task-manager-token`.

## CI/CD (GitHub Actions)

Пайплайн: `reject-direct-push → backend-tests + frontend-tests → deploy`.
Деплой: сборка Docker-образов → пуш в GHCR → SSH на сервер → `docker compose pull && up -d`.

## Отслеживание задач

Статусы задач в `docs/tasks/current.md`: `todo` → `in_progress` → `review` → перенос в `done.md`.
Перед началом — прочитать `current.md`, сменить статус. После завершения — запустить тесты, перенести задачу, указать дату и затронутые файлы.
