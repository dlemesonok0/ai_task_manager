# Профилирование AI Task Manager

## Backend

Все команды из `backend/`:

```bash
cd backend
```

### Быстрый старт

```bash
# Полный отчёт (система + импорты + память + CPU + эндпоинты + docker + frontend)
uv run python profile.py

# Только конкретный раздел
uv run python profile.py imports      # пошаговый замер памяти по модулям
uv run python profile.py memory       # tracemalloc с топ-10 строк
uv run python profile.py cpu          # pyinstrument flame graph
uv run python profile.py endpoints    # латентность эндпоинтов
uv run python profile.py docker       # запущенные контейнеры и образы
uv run python profile.py frontend     # сборка + размер бандла
uv run python profile.py system       # инфо о системе
```

### Профилирование конкретного запроса

Запусти сервер с включённым профилированием:

```bash
PROFILE=1 uv run uvicorn main:app --reload
```

Добавь `?profile=1` к любому запросу:

```bash
curl "http://localhost:8000/api/health/ai?profile=1"
```

Открой HTML-отчёт с flame graph:

```bash
curl http://localhost:8000/profile > report.html
start report.html  # Windows
```

### Зависимости

```bash
uv pip install pyinstrument memory_profiler psutil
```

Или через dev-группу (уже в `pyproject.toml`):

```bash
uv sync --group dev
```

---

## Frontend

Все команды из `frontend/`:

```bash
cd frontend
```

### Bundle analysis

```bash
npm run analyze
```

После сборки откроется `dist/stats.html` — интерактивная визуализация бандла с размерами (raw, gzip, brotli).

### Ручное профилирование

1. `npm run dev` — запусти dev-сервер
2. Открой Chrome DevTools → Performance → Record
3. Повтори действия в UI → Stop → анализируй flame chart
4. Memory tab → Heap snapshot для поиска утечек

---

## Docker

### Текущее потребление

```bash
docker stats --no-stream
```

### Размер образов

```bash
docker images | grep ai_task_manager
```

---

## Целевые метрики (TASK-009)

| Метрика | Сейчас | Цель |
|---|---|---|
| Backend Docker | 727 MB | ≤ 300 MB |
| Backend RSS | 87 MB | ≤ 60 MB |
| Frontend JS (gzip) | 64 KB | ≤ 50 KB |
