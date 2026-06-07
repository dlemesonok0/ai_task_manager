import json
import os
import secrets
import threading
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
from psycopg.rows import dict_row


DATABASE_URL = os.getenv("DATABASE_URL", "postgres://ai_task_manager:change-me@localhost:5432/ai_task_manager")
_lock = threading.Lock()
_initialized = False


def _connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def _now() -> datetime:
    return datetime.now(UTC)


def init_db() -> None:
    global _initialized
    if _initialized:
        return
    with _lock, _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id BIGSERIAL PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_integrations (
                    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    todoist_api_token TEXT,
                    google_token_json TEXT,
                    telegram_bot_token TEXT,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS telegram_user_links (
                    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    telegram_user_id BIGINT NOT NULL UNIQUE,
                    telegram_username TEXT,
                    linked_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS telegram_link_codes (
                    code TEXT PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expires_at TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS cached_tasks (
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    due TEXT,
                    payload JSONB NOT NULL,
                    synced_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (user_id, id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS cached_events (
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    id TEXT NOT NULL,
                    calendar_id TEXT NOT NULL,
                    summary TEXT,
                    start_value TEXT,
                    end_value TEXT,
                    payload JSONB NOT NULL,
                    synced_at TIMESTAMPTZ NOT NULL,
                    PRIMARY KEY (user_id, id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_state (
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    resource TEXT NOT NULL,
                    synced_at TIMESTAMPTZ NOT NULL,
                    item_count INTEGER NOT NULL,
                    PRIMARY KEY (user_id, resource)
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cached_events_start ON cached_events(user_id, start_value)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_telegram_link_codes_user ON telegram_link_codes(user_id)")
    _initialized = True


def ensure_initialized() -> None:
    if not _initialized:
        init_db()


def create_user(username: str, password_hash: str) -> dict[str, Any]:
    ensure_initialized()
    with _lock, _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (username, password_hash, created_at)
                VALUES (%s, %s, %s)
                RETURNING id, username
                """,
                (username, password_hash, _now()),
            )
            return cursor.fetchone()


def get_user_by_username(username: str) -> dict[str, Any] | None:
    ensure_initialized()
    with _lock, _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, username, password_hash FROM users WHERE username = %s", (username,))
            return cursor.fetchone()


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    ensure_initialized()
    with _lock, _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, username FROM users WHERE id = %s", (user_id,))
            return cursor.fetchone()


def create_telegram_link_code(user_id: int, ttl_minutes: int = 15) -> dict[str, Any]:
    ensure_initialized()
    now = _now()
    expires_at = now + timedelta(minutes=ttl_minutes)
    with _lock, _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM telegram_link_codes WHERE user_id = %s OR expires_at <= %s", (user_id, now))
            while True:
                code = secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8].upper()
                try:
                    cursor.execute(
                        """
                        INSERT INTO telegram_link_codes (code, user_id, expires_at, created_at)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (code, user_id, expires_at, now),
                    )
                    break
                except psycopg.errors.UniqueViolation:
                    connection.rollback()
                    continue
    return {"code": code, "expires_at": expires_at.isoformat()}


def get_telegram_link(user_id: int) -> dict[str, Any] | None:
    ensure_initialized()
    with _lock, _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT user_id, telegram_user_id, telegram_username, linked_at
                FROM telegram_user_links
                WHERE user_id = %s
                """,
                (user_id,),
            )
            row = cursor.fetchone()
    return _telegram_link_payload(row)


def get_user_by_telegram_id(telegram_user_id: int) -> dict[str, Any] | None:
    ensure_initialized()
    with _lock, _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.id, u.username, l.telegram_user_id, l.telegram_username, l.linked_at
                FROM telegram_user_links l
                JOIN users u ON u.id = l.user_id
                WHERE l.telegram_user_id = %s
                """,
                (telegram_user_id,),
            )
            row = cursor.fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "telegram_user_id": row["telegram_user_id"],
        "telegram_username": row["telegram_username"],
        "linked_at": row["linked_at"].isoformat() if row["linked_at"] else None,
    }


def consume_telegram_link_code(code: str, telegram_user_id: int, telegram_username: str | None = None) -> dict[str, Any] | None:
    ensure_initialized()
    normalized_code = code.strip().upper()
    now = _now()
    with _lock, _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.user_id, u.username
                FROM telegram_link_codes c
                JOIN users u ON u.id = c.user_id
                WHERE c.code = %s AND c.expires_at > %s
                """,
                (normalized_code, now),
            )
            row = cursor.fetchone()
            if not row:
                cursor.execute("DELETE FROM telegram_link_codes WHERE code = %s OR expires_at <= %s", (normalized_code, now))
                return None

            cursor.execute("DELETE FROM telegram_user_links WHERE telegram_user_id = %s", (telegram_user_id,))
            cursor.execute(
                """
                INSERT INTO telegram_user_links (user_id, telegram_user_id, telegram_username, linked_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    telegram_user_id = EXCLUDED.telegram_user_id,
                    telegram_username = EXCLUDED.telegram_username,
                    linked_at = EXCLUDED.linked_at
                """,
                (row["user_id"], telegram_user_id, telegram_username, now),
            )
            cursor.execute("DELETE FROM telegram_link_codes WHERE user_id = %s", (row["user_id"],))
            return {"id": row["user_id"], "username": row["username"]}


def unlink_telegram_user(user_id: int) -> None:
    ensure_initialized()
    with _lock, _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM telegram_user_links WHERE user_id = %s", (user_id,))


def upsert_integrations(
    user_id: int,
    todoist_api_token: str | None = None,
    google_token_json: str | None = None,
    telegram_bot_token: str | None = None,
) -> None:
    ensure_initialized()
    current = get_integrations(user_id, include_secrets=True)
    values = {
        "todoist_api_token": todoist_api_token if todoist_api_token is not None else current.get("todoist_api_token"),
        "google_token_json": google_token_json if google_token_json is not None else current.get("google_token_json"),
        "telegram_bot_token": telegram_bot_token if telegram_bot_token is not None else current.get("telegram_bot_token"),
    }
    with _lock, _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO user_integrations (user_id, todoist_api_token, google_token_json, telegram_bot_token, updated_at)
                VALUES (%(user_id)s, %(todoist_api_token)s, %(google_token_json)s, %(telegram_bot_token)s, %(updated_at)s)
                ON CONFLICT (user_id) DO UPDATE SET
                    todoist_api_token = EXCLUDED.todoist_api_token,
                    google_token_json = EXCLUDED.google_token_json,
                    telegram_bot_token = EXCLUDED.telegram_bot_token,
                    updated_at = EXCLUDED.updated_at
                """,
                {"user_id": user_id, **values, "updated_at": _now()},
            )


def get_integrations(user_id: int, include_secrets: bool = False) -> dict[str, Any]:
    ensure_initialized()
    with _lock, _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT todoist_api_token, google_token_json, telegram_bot_token, updated_at
                FROM user_integrations
                WHERE user_id = %s
                """,
                (user_id,),
            )
            row = cursor.fetchone()
    if not row:
        result = {
            "todoist_connected": False,
            "google_connected": False,
            "telegram_connected": False,
            "updated_at": None,
        }
        if include_secrets:
            result.update({"todoist_api_token": None, "google_token_json": None, "telegram_bot_token": None})
        return result

    result = {
        "todoist_connected": bool(row["todoist_api_token"]),
        "google_connected": bool(row["google_token_json"]),
        "telegram_connected": bool(row["telegram_bot_token"]),
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }
    if include_secrets:
        result.update(
            {
                "todoist_api_token": row["todoist_api_token"],
                "google_token_json": row["google_token_json"],
                "telegram_bot_token": row["telegram_bot_token"],
            }
        )
    return result


def replace_tasks(user_id: int, tasks: list[dict[str, Any]]) -> None:
    ensure_initialized()
    synced_at = _now()
    with _lock, _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM cached_tasks WHERE user_id = %s", (user_id,))
            cursor.executemany(
                """
                INSERT INTO cached_tasks (user_id, id, content, priority, due, payload, synced_at)
                VALUES (%(user_id)s, %(id)s, %(content)s, %(priority)s, %(due)s, %(payload)s, %(synced_at)s)
                """,
                [
                    {
                        "user_id": user_id,
                        "id": task["id"],
                        "content": task["content"],
                        "priority": task["priority"],
                        "due": task.get("due"),
                        "payload": json.dumps(task, ensure_ascii=False),
                        "synced_at": synced_at,
                    }
                    for task in tasks
                ],
            )
            _upsert_sync_state(cursor, user_id, "tasks", synced_at, len(tasks))


def upsert_task(user_id: int, task: dict[str, Any]) -> None:
    ensure_initialized()
    synced_at = _now()
    with _lock, _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO cached_tasks (user_id, id, content, priority, due, payload, synced_at)
                VALUES (%(user_id)s, %(id)s, %(content)s, %(priority)s, %(due)s, %(payload)s, %(synced_at)s)
                ON CONFLICT (user_id, id) DO UPDATE SET
                    content = EXCLUDED.content,
                    priority = EXCLUDED.priority,
                    due = EXCLUDED.due,
                    payload = EXCLUDED.payload,
                    synced_at = EXCLUDED.synced_at
                """,
                {
                    "user_id": user_id,
                    "id": task["id"],
                    "content": task["content"],
                    "priority": task["priority"],
                    "due": task.get("due"),
                    "payload": json.dumps(task, ensure_ascii=False),
                    "synced_at": synced_at,
                },
            )


def delete_task(user_id: int, task_id: str) -> None:
    ensure_initialized()
    with _lock, _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM cached_tasks WHERE user_id = %s AND id = %s", (user_id, task_id))


def get_tasks(user_id: int) -> list[dict[str, Any]]:
    ensure_initialized()
    with _lock, _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT payload FROM cached_tasks WHERE user_id = %s ORDER BY synced_at, id", (user_id,))
            rows = cursor.fetchall()
    return [_payload(row["payload"]) for row in rows]


def replace_events(user_id: int, events: list[dict[str, Any]]) -> None:
    ensure_initialized()
    synced_at = _now()
    with _lock, _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM cached_events WHERE user_id = %s", (user_id,))
            cursor.executemany(
                """
                INSERT INTO cached_events (user_id, id, calendar_id, summary, start_value, end_value, payload, synced_at)
                VALUES (%(user_id)s, %(id)s, %(calendar_id)s, %(summary)s, %(start_value)s, %(end_value)s, %(payload)s, %(synced_at)s)
                """,
                [_event_row(user_id, event, synced_at) for event in events],
            )
            _upsert_sync_state(cursor, user_id, "events", synced_at, len(events))


def upsert_event(user_id: int, event: dict[str, Any]) -> None:
    ensure_initialized()
    synced_at = _now()
    with _lock, _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO cached_events (user_id, id, calendar_id, summary, start_value, end_value, payload, synced_at)
                VALUES (%(user_id)s, %(id)s, %(calendar_id)s, %(summary)s, %(start_value)s, %(end_value)s, %(payload)s, %(synced_at)s)
                ON CONFLICT (user_id, id) DO UPDATE SET
                    calendar_id = EXCLUDED.calendar_id,
                    summary = EXCLUDED.summary,
                    start_value = EXCLUDED.start_value,
                    end_value = EXCLUDED.end_value,
                    payload = EXCLUDED.payload,
                    synced_at = EXCLUDED.synced_at
                """,
                _event_row(user_id, event, synced_at),
            )


def get_events(user_id: int) -> list[dict[str, Any]]:
    ensure_initialized()
    with _lock, _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT payload FROM cached_events WHERE user_id = %s ORDER BY COALESCE(start_value, '')",
                (user_id,),
            )
            rows = cursor.fetchall()
    return [_payload(row["payload"]) for row in rows]


def get_sync_state(user_id: int) -> dict[str, dict[str, Any]]:
    ensure_initialized()
    with _lock, _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT resource, synced_at, item_count FROM sync_state WHERE user_id = %s",
                (user_id,),
            )
            rows = cursor.fetchall()
    return {
        row["resource"]: {
            "synced_at": row["synced_at"].isoformat(),
            "item_count": row["item_count"],
        }
        for row in rows
    }


def clear_cache() -> None:
    ensure_initialized()
    with _lock, _connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE cached_tasks, cached_events, sync_state, user_integrations, users RESTART IDENTITY CASCADE")


def _event_row(user_id: int, event: dict[str, Any], synced_at: datetime) -> dict[str, Any]:
    start = event.get("start", {})
    end = event.get("end", {})
    return {
        "user_id": user_id,
        "id": event["id"],
        "calendar_id": event.get("calendarId") or "primary",
        "summary": event.get("summary"),
        "start_value": start.get("dateTime") or start.get("date"),
        "end_value": end.get("dateTime") or end.get("date"),
        "payload": json.dumps(event, ensure_ascii=False),
        "synced_at": synced_at,
    }


def _upsert_sync_state(cursor: psycopg.Cursor, user_id: int, resource: str, synced_at: datetime, item_count: int) -> None:
    cursor.execute(
        """
        INSERT INTO sync_state (user_id, resource, synced_at, item_count)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id, resource) DO UPDATE SET
            synced_at = EXCLUDED.synced_at,
            item_count = EXCLUDED.item_count
        """,
        (user_id, resource, synced_at, item_count),
    )


def _payload(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _telegram_link_payload(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "user_id": row["user_id"],
        "telegram_user_id": row["telegram_user_id"],
        "telegram_username": row["telegram_username"],
        "linked_at": row["linked_at"].isoformat() if row["linked_at"] else None,
    }
