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
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS cached_tasks (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                priority INTEGER NOT NULL,
                due TEXT,
                payload TEXT NOT NULL,
                synced_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cached_events (
                id TEXT PRIMARY KEY,
                calendar_id TEXT NOT NULL,
                summary TEXT,
                start_value TEXT,
                end_value TEXT,
                payload TEXT NOT NULL,
                synced_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sync_state (
                resource TEXT PRIMARY KEY,
                synced_at TEXT NOT NULL,
                item_count INTEGER NOT NULL
            );
            """
        )


def replace_tasks(tasks: list[dict[str, Any]]) -> None:
    synced_at = _now()
    with _lock, _connect() as connection:
        connection.execute("DELETE FROM cached_tasks")
        connection.executemany(
            """
            INSERT INTO cached_tasks (id, content, priority, due, payload, synced_at)
            VALUES (:id, :content, :priority, :due, :payload, :synced_at)
            """,
            [
                {
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
        _upsert_sync_state(connection, "tasks", synced_at, len(tasks))


def upsert_task(task: dict[str, Any]) -> None:
    synced_at = _now()
    with _lock, _connect() as connection:
        connection.execute(
            """
            INSERT INTO cached_tasks (id, content, priority, due, payload, synced_at)
            VALUES (:id, :content, :priority, :due, :payload, :synced_at)
            ON CONFLICT(id) DO UPDATE SET
                content = excluded.content,
                priority = excluded.priority,
                due = excluded.due,
                payload = excluded.payload,
                synced_at = excluded.synced_at
            """,
            {
                "id": task["id"],
                "content": task["content"],
                "priority": task["priority"],
                "due": task.get("due"),
                "payload": json.dumps(task, ensure_ascii=False),
                "synced_at": synced_at,
            },
        )


def get_tasks() -> list[dict[str, Any]]:
    with _lock, _connect() as connection:
        rows = connection.execute("SELECT payload FROM cached_tasks ORDER BY rowid").fetchall()
    return [json.loads(row["payload"]) for row in rows]


def replace_events(events: list[dict[str, Any]]) -> None:
    synced_at = _now()
    with _lock, _connect() as connection:
        connection.execute("DELETE FROM cached_events")
        connection.executemany(
            """
            INSERT INTO cached_events (id, calendar_id, summary, start_value, end_value, payload, synced_at)
            VALUES (:id, :calendar_id, :summary, :start_value, :end_value, :payload, :synced_at)
            """,
            [_event_row(event, synced_at) for event in events],
        )
        _upsert_sync_state(connection, "events", synced_at, len(events))


def upsert_event(event: dict[str, Any]) -> None:
    synced_at = _now()
    with _lock, _connect() as connection:
        connection.execute(
            """
            INSERT INTO cached_events (id, calendar_id, summary, start_value, end_value, payload, synced_at)
            VALUES (:id, :calendar_id, :summary, :start_value, :end_value, :payload, :synced_at)
            ON CONFLICT(id) DO UPDATE SET
                calendar_id = excluded.calendar_id,
                summary = excluded.summary,
                start_value = excluded.start_value,
                end_value = excluded.end_value,
                payload = excluded.payload,
                synced_at = excluded.synced_at
            """,
            _event_row(event, synced_at),
        )


def get_events() -> list[dict[str, Any]]:
    with _lock, _connect() as connection:
        rows = connection.execute(
            "SELECT payload FROM cached_events ORDER BY COALESCE(start_value, '')"
        ).fetchall()
    return [json.loads(row["payload"]) for row in rows]


def get_sync_state() -> dict[str, dict[str, Any]]:
    with _lock, _connect() as connection:
        rows = connection.execute("SELECT resource, synced_at, item_count FROM sync_state").fetchall()
    return {
        row["resource"]: {"synced_at": row["synced_at"], "item_count": row["item_count"]}
        for row in rows
    }


def clear_cache() -> None:
    with _lock, _connect() as connection:
        connection.execute("DELETE FROM cached_tasks")
        connection.execute("DELETE FROM cached_events")
        connection.execute("DELETE FROM sync_state")


def _event_row(event: dict[str, Any], synced_at: str) -> dict[str, Any]:
    start = event.get("start", {})
    end = event.get("end", {})
    return {
        "id": event["id"],
        "calendar_id": event.get("calendarId") or "primary",
        "summary": event.get("summary"),
        "start_value": start.get("dateTime") or start.get("date"),
        "end_value": end.get("dateTime") or end.get("date"),
        "payload": json.dumps(event, ensure_ascii=False),
        "synced_at": synced_at,
    }


def _upsert_sync_state(connection: sqlite3.Connection, resource: str, synced_at: str, item_count: int) -> None:
    connection.execute(
        """
        INSERT INTO sync_state (resource, synced_at, item_count)
        VALUES (?, ?, ?)
        ON CONFLICT(resource) DO UPDATE SET
            synced_at = excluded.synced_at,
            item_count = excluded.item_count
        """,
        (resource, synced_at, item_count),
    )


init_db()
