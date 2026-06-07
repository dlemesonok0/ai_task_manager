# SCA Trivy report

Дата: 2026-06-07

Команды:

```powershell
trivy fs --config trivy.yaml --format table --output reports/security/trivy-report.txt .
trivy fs --config trivy.yaml --format json --output reports/security/trivy-report.json .
```

Настроенные проверки:

- `vuln`: зависимости Python и Node.js по lockfiles.
- `secret`: случайно закоммиченные токены и ключи.
- `misconfig`: Dockerfile, compose и YAML-конфигурации.
- Severity gate: `HIGH`, `CRITICAL`.
- `ignore-unfixed: true`: не блокировать по CVE без доступного исправления, но фиксировать их в отчете.

Как работать с найденными уязвимостями:

- `CRITICAL`: обновить dependency или заменить пакет до деплоя.
- `HIGH`: оценить достижимость в приложении; если пакет попадает в runtime path, обновить в той же задаче.
- Dev-only dependency: обновить при наличии фиксированной версии; если exploitability низкая, оформить accept-risk с причиной.
- Misconfig/secret: исправлять конфигурацию или удалять секрет из репозитория, затем ротация секрета.

Локальная демонстрация SCA:

- `npm audit` сохранил отчеты в `reports/security/npm-audit-report.txt` и `reports/security/npm-audit-report.json`.
- Найден `brace-expansion` с `moderate` severity; исправление: `npm audit fix`.
- `pip-audit` сохранил отчет в `reports/security/pip-audit-report.json`.
- Найдены 2 уязвимости в `aiohttp 3.13.5`; исправление: обновить до `aiohttp 3.14.0` через зависимость, которая подтягивает `aiohttp`.
