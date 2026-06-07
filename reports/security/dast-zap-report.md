# DAST OWASP ZAP report

Дата: 2026-06-07

Инструмент: OWASP ZAP Baseline Scan.

Команды:

```powershell
docker compose up -d db api frontend
docker run --rm --network ai_task_manager_default -v ${PWD}/reports/security:/zap/wrk/:rw ghcr.io/zaproxy/zaproxy:stable zap-baseline.py -t http://frontend -c zap-baseline.conf -r zap-report.html -J zap-report.json
```

Настроенные проверки:

- `10020`: Missing Anti-clickjacking Header, режим `FAIL`.
- `10038`: Content Security Policy Header Not Set, режим `FAIL`.
- `10021`: X-Content-Type-Options Header Missing, режим `WARN`.
- `10010`, `10023`, `10024`, `10027`: disclosure checks, режим `WARN`.
- Cookie/cache/HSTS проверки оставлены в `WARN`, потому что локальный стенд работает по HTTP.

Ожидаемые демонстрационные находки:

- В текущем `frontend/nginx.conf` не настроены security headers, поэтому ZAP должен показать alerts по clickjacking/CSP/header hardening.

Как исправлять при реальной доработке:

- Добавить `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` и базовый `Content-Security-Policy` в nginx-конфигурацию frontend.
