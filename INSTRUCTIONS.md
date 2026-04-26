# Инструкция по локальному запуску проекта

Этот проект состоит из двух основных частей: **Backend** (FastAPI + Telegram Bot) и **Frontend** (React + Vite).

## Предварительные требования
- Установленный [uv](https://github.com/astral-sh/uv) (для бекенда)
- Установленный [Node.js](https://nodejs.org/) (для фронтенда)

---

## 1. Настройка Бекенда

Перейдите в директорию бекенда:
```powershell
cd backend
```

### Настройка окружения (.env)
Создайте или отредактируйте файл `.env` в папке `backend` и добавьте ваши API ключи:
```env
TELEGRAM_BOT_TOKEN=your_token_here
TODOIST_API_TOKEN=your_token_here
GEMINI_API_KEY=your_token_here
```

### Установка зависимостей
Благодаря `uv`, установка происходит мгновенно:
```powershell
uv sync
```

### Запуск API
API будет доступно по адресу `http://localhost:8000`:
```powershell
uv run uvicorn main:app --reload
```

### Запуск Telegram Бота
Запускается в отдельном терминале:
```powershell
uv run python bot.py
```

### Запуск тестов
```powershell
uv run pytest
```

---

## 2. Настройка Фронтенда

Перейдите в директорию фронтенда:
```powershell
cd frontend
```

### Установка зависимостей
```powershell
npm install
```

### Запуск в режиме разработки
Фронтенд будет доступен по адресу `http://localhost:5173`:
```powershell
npm run dev
```

---

## Полезные советы
- Если команда `uv` не найдена в PowerShell, используйте полный путь: `C:\Users\dleme\.local\bin\uv.exe`
- Для работы Google Calendar убедитесь, что файл `credentials.json` находится в папке `backend`.
