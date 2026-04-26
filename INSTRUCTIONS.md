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

## 3. Настройка Google Calendar
Для работы с календарем требуется OAuth2 авторизация.

1.  **credentials.json**: Положите файл секретов из Google Cloud Console в папку `backend`.
2.  **Первичная авторизация**:
    *   Запустите бэкенд локально: `uv run uvicorn main:app`.
    *   Перейдите по адресу `http://localhost:8000/api/events`.
    *   В консоли появится ссылка или откроется браузер. Зайдите в аккаунт.
3.  **token.json**: После авторизации в папке `backend` появится файл `token.json`.
4.  **Деплой на сервер**:
    *   Для работы календаря на удаленном сервере ОБЯЗАТЕЛЬНО скопируйте `token.json` в папку `backend` на сервере.
    *   Без этого файла сервер не сможет получить доступ к календарю, так как не сможет открыть браузер для входа.

---

## Полезные советы
- Если команда `uv` не найдена в PowerShell, используйте полный путь: `C:\Users\dleme\.local\bin\uv.exe`
- Убедитесь, что порты 8000 и 5173 не заняты другими приложениями.
