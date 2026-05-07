import json
import logging
import os
import time
from collections import deque
from datetime import datetime, UTC
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
LOG_FILE = LOG_DIR / os.getenv("LOG_FILE_NAME", "app.log")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", "5242880"))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key.startswith("_") and key != "_extra":
                continue
            if key == "_extra" and isinstance(value, dict):
                payload.update(value)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)

    if getattr(root_logger, "_ai_task_manager_logging_configured", False):
        return

    formatter = JsonFormatter()

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger._ai_task_manager_logging_configured = True


def bind_extra(**extra: Any) -> dict[str, Any]:
    return {"_extra": extra}


def read_recent_logs(limit: int = 200) -> list[dict[str, Any]]:
    if not LOG_FILE.exists():
        return []

    lines = deque(maxlen=max(1, min(limit, 1000)))
    with LOG_FILE.open("r", encoding="utf-8") as log_file:
        for line in log_file:
            if line.strip():
                lines.append(line)

    entries: list[dict[str, Any]] = []
    for line in lines:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            entries.append({"timestamp": None, "level": "UNKNOWN", "message": line.strip()})
    return entries


def log_path() -> Path:
    return LOG_FILE


def monotonic_ms(start_time: float) -> int:
    return round((time.perf_counter() - start_time) * 1000)
