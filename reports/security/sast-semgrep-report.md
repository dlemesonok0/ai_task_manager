# SAST Semgrep report

Дата: 2026-06-07

Команда:

```powershell
semgrep scan --config .semgrep.yml backend frontend
```

Настроенные правила:

- `python.fastapi.wildcard-cors-with-credentials`: запрещает `allow_origins=["*"]` вместе с `allow_credentials=True`.
- `python.auth.hardcoded-auth-secret`: ищет hardcoded/default authentication secrets.
- `python.debug.profile-endpoint-without-env-guard`: проверяет guard для debug profile endpoint.
- `python.subprocess.shell-true`: запрещает `subprocess.*(..., shell=True)`.
- `typescript.react.dangerous-html`: ищет потенциальный XSS через `dangerouslySetInnerHTML`.

Ожидаемые демонстрационные находки:

- `backend/main.py`: wildcard CORS вместе с `allow_credentials=True`.
- `backend/services/auth_service.py`: fallback JWT secret `dev-only-auth-secret`.

Как исправлять при реальной доработке:

- Заменить `allow_origins=["*"]` на список origins из env-переменной.
- Сделать `AUTH_SECRET_KEY` обязательным и проверять минимальную длину секрета.
