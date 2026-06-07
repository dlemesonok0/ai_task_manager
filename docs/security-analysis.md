# Анализ безопасности

Дата: 2026-06-07

## SAST

Инструмент: Semgrep.

Конфигурация: стандартные rulesets `p/security-audit`, `p/python`, `p/javascript` и проектные правила `.semgrep.yml`.

Покрытие:

- Стандартные Semgrep checks для Python и JavaScript/TypeScript.
- FastAPI CORS misconfiguration.
- Hardcoded/default auth secret.
- Debug/profile endpoint без env guard.
- `subprocess` с `shell=True`.
- React `dangerouslySetInnerHTML`.

Ожидаемые демонстрационные срабатывания:

- В `backend/main.py` разрешен wildcard CORS при `allow_credentials=True`.
- В `backend/services/auth_service.py` есть fallback secret для JWT.

Как исправлять:

- Заменить wildcard CORS на список origins из env.
- Сделать `AUTH_SECRET_KEY` обязательным и проверять минимальную длину.

## DAST

Инструмент: OWASP ZAP Baseline Scan.

Конфигурация: `zap-baseline.conf`.

Цель сканирования: frontend container, который проксирует `/api` в backend.

Проверки:

- Anti-clickjacking header.
- Content Security Policy.
- X-Content-Type-Options.
- Disclosure и cookie/cache checks.

Ожидаемое демонстрационное срабатывание:

- В `frontend/nginx.conf` нет security headers, поэтому ZAP должен показать alerts по CSP, anti-clickjacking и header hardening.

Как исправлять:

- Добавить `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Content-Security-Policy`.

## SCA

Инструмент: Trivy.

Конфигурация: `trivy.yaml`.

Покрытие:

- Python dependencies из `backend/uv.lock`.
- Node dependencies из `frontend/package-lock.json`.
- Dockerfile, compose и YAML misconfigurations.
- Secret scanning.

Политика обработки:

- `CRITICAL`: блокирует релиз до обновления или удаления зависимости.
- `HIGH`: блокирует релиз, если зависимость достижима в runtime path.
- Dev-only уязвимости исправляются обновлением dev dependency или документируются как accept-risk.
- Misconfiguration и secrets исправляются в конфигурации; для реального секрета требуется ротация.

Локальная демонстрация:

- `npm audit` нашел `brace-expansion` с `moderate` severity. Это dev/build dependency path; исправление — `npm audit fix` после проверки lockfile diff.
- `pip-audit` нашел 2 CVE в `aiohttp 3.13.5`, фикс доступен в `3.14.0`. Для приложения это важно, потому что `aiohttp` приходит через `aiogram`; обновлять нужно совместимо с bot runtime.

## CI/CD

В `.github/workflows/run-tests.yml` добавлены jobs:

- `sast-semgrep`.
- `sca-trivy`.
- `dast-zap`.

`deploy` зависит от тестов и security jobs. Отчеты загружаются как GitHub Actions artifacts и дублируются в `$GITHUB_STEP_SUMMARY`.
