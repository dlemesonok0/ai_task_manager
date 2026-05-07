import json
import os
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DATABASE_PATH = os.getenv("DATABASE_PATH", "data/app.db")
_lock = threading.Lock()


def _db_path() -> str:
    if DATABASE_PATH != ":memory:":
        Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    return DATABASE_PATH


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(_db_path(), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def _now() -> str:
    return datetime.now(UTC).isoformat()


def init_db() -> None:
    with _lock, _connect() as connection:
        _drop_legacy_cache_tables(connection)
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS cached_tasks (
                user_id INTEGER NOT NULL,
                id TEXT NOT NULL,
                content TEXT NOT NULL,
                priority INTEGER NOT NULL,
                due TEXT,
                payload TEXT NOT NULL,
                synced_at TEXT NOT NULL,
                PRIMARY KEY (user_id, id)
            );

            CREATE TABLE IF NOT EXISTS cached_events (
                user_id INTEGER NOT NULL,
                id TEXT NOT NULL,
                calendar_id TEXT NOT NULL,
                summary TEXT,
                start_value TEXT,
                end_value TEXT,
                payload TEXT NOT NULL,
                synced_at TEXT NOT NULL,
                PRIMARY KEY (user_id, id)
            );

            CREATE TABLE IF NOT EXISTS sync_state (
                user_id INTEGER NOT NULL,
                resource TEXT NOT NULL,
                synced_at TEXT NOT NULL,
                item_count INTEGER NOT NULL,
                PRIMARY KEY (user_id, resource)
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_integrations (
                user_id INTEGER PRIMARY KEY,
                todoist_api_token TEXT,
                google_token_json TEXT,
                telegram_bot_token TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )


def _drop_legacy_cache_tables(connection: sqlite3.Connection) -> None:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'cached_tasks'"
    ).fetchone()
    if not row:
        return
    columns = {
        column["name"]
        for column in connection.execute("PRAGMA table_info(cached_tasks)").fetchall()
    }
    if "user_id" in columns:
        return
    connection.executescript(
        """
        DROP TABLE IF EXISTS cached_tasks;
        DROP TABLE IF EXISTS cached_events;
        DROP TABLE IF EXISTS sync_state;
        """
    )


def create_user(username: str, password_hash: str) -> dict[str, Any]:
    with _lock, _connect() as connection:
        cursor = connection.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, password_hash, _now()),
        )
        return {"id": cursor.lastrowid, "username": username}


def get_user_by_username(username: str) -> dict[str, Any] | None:
    with _lock, _connect() as connection:
        row = connection.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict[str, Any] | None:
    with _lock, _connect() as connection:
        row = connection.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def upsert_integrations(
    user_id: int,
    todoist_api_token: str | None = None,
    google_token_json: str | None = None,
    telegram_bot_token: str | None = None,
) -> None:
    current = get_integrations(user_id, include_secrets=True)
    values = {
        "todoist_api_token": todoist_api_token if todoist_api_token is not None else current.get("todoist_api_token"),
        "google_token_json": google_token_json if google_token_json is not None else current.get("google_token_json"),
        "telegram_bot_token": telegram_bot_token if telegram_bot_token is not None else current.get("telegram_bot_token"),
    }
    with _lock, _connect() as connection:
        connection.execute(
            """
            INSERT INTO user_integrations (user_id, todoist_api_token, google_token_json, telegram_bot_token, updated_at)
            VALUES (:user_id, :todoist_api_token, :google_token_json, :telegram_bot_token, :updated_at)
            ON CONFLICT(user_id) DO UPDATE SET
                todoist_api_token = excluded.todoist_api_token,
                google_token_json = excluded.google_token_json,
                telegram_bot_token = excluded.telegram_bot_token,
                updated_at = excluded.updated_at
            """,
            {"user_id": user_id, **values, "updated_at": _now()},
        )


def get_integrations(user_id: int, include_secrets: bool = False) -> dict[str, Any]:
    with _lock, _connect() as connection:
        row = connection.execute(
            """
            SELECT todoist_api_token, google_token_json, telegram_bot_token, updated_at
            FROM user_integrations
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
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
        "updated_at": row["updated_at"],
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
    synced_at = _now()
    with _lock, _connect() as connection:
        connection.execute("DELETE FROM cached_tasks WHERE user_id = ?", (user_id,))
        connection.executemany(
            """
            INSERT INTO cached_tasks (user_id, id, content, priority, due, payload, synced_at)
            VALUES (:user_id, :id, :content, :priority, :due, :payload, :synced_at)
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
        _upsert_sync_state(connection, user_id, "tasks", synced_at, len(tasks))


def upsert_task(user_id: int, task: dict[str, Any]) -> None:
    synced_at = _now()
    with _lock, _connect() as connection:
        connection.execute(
            """
            INSERT INTO cached_tasks (user_id, id, content, priority, due, payload, synced_at)
            VALUES (:user_id, :id, :content, :priority, :due, :payload, :synced_at)
            ON CONFLICT(user_id, id) DO UPDATE SET
                content = excluded.content,
                priority = excluded.priority,
                due = excluded.due,
                payload = excluded.payload,
                synced_at = excluded.synced_at
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


def get_tasks(user_id: int) -> list[dict[str, Any]]:
    with _lock, _connect() as connection:
        rows = connection.execute(
            "SELECT payload FROM cached_tasks WHERE user_id = ? ORDER BY rowid",
            (user_id,),
        ).fetchall()
    return [json.loads(row["payload"]) for row in rows]


def replace_events(user_id: int, events: list[dict[str, Any]]) -> None:
    synced_at = _now()
    with _lock, _connect() as connection:
        connection.execute("DELETE FROM cached_events WHERE user_id = ?", (user_id,))
        connection.executemany(
            """
            INSERT INTO cached_events (user_id, id, calendar_id, summary, start_value, end_value, payload, synced_at)
            VALUES (:user_id, :id, :calendar_id, :summary, :start_value, :end_value, :payload, :synced_at)
            """,
            [_event_row(user_id, event, synced_at) for event in events],
        )
        _upsert_sync_state(connection, user_id, "events", synced_at, len(events))


def upsert_event(user_id: int, event: dict[str, Any]) -> None:
    synced_at = _now()
    with _lock, _connect() as connection:
        connection.execute(
            """
            INSERT INTO cached_events (user_id, id, calendar_id, summary, start_value, end_value, payload, synced_at)
            VALUES (:user_id, :id, :calendar_id, :summary, :start_value, :end_value, :payload, :synced_at)
            ON CONFLICT(user_id, id) DO UPDATE SET
                calendar_id = excluded.calendar_id,
                summary = excluded.summary,
                start_value = excluded.start_value,
                end_value = excluded.end_value,
                payload = excluded.payload,
                synced_at = excluded.synced_at
            """,
            _event_row(user_id, event, synced_at),
        )


def get_events(user_id: int) -> list[dict[str, Any]]:
    with _lock, _connect() as connection:
        rows = connection.execute(
            "SELECT payload FROM cached_events WHERE user_id = ? ORDER BY COALESCE(start_value, '')",
            (user_id,),
        ).fetchall()
    return [json.loads(row["payload"]) for row in rows]


def get_sync_state(user_id: int) -> dict[str, dict[str, Any]]:
    with _lock, _connect() as connection:
        rows = connection.execute(
            "SELECT resource, synced_at, item_count FROM sync_state WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    return {
        row["resource"]: {"synced_at": row["synced_at"], "item_count": row["item_count"]}
        for row in rows
    }


def clear_cache() -> None:
    with _lock, _connect() as connection:
        connection.execute("DELETE FROM cached_tasks")
        connection.execute("DELETE FROM cached_events")
        connection.execute("DELETE FROM sync_state")
        connection.execute("DELETE FROM user_integrations")
        connection.execute("DELETE FROM users")


def _event_row(user_id: int, event: dict[str, Any], synced_at: str) -> dict[str, Any]:
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


def _upsert_sync_state(connection: sqlite3.Connection, user_id: int, resource: str, synced_at: str, item_count: int) -> None:
    connection.execute(
        """
        INSERT INTO sync_state (user_id, resource, synced_at, item_count)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, resource) DO UPDATE SET
            synced_at = excluded.synced_at,
            item_count = excluded.item_count
        """,
        (user_id, resource, synced_at, item_count),
    )


init_db()
