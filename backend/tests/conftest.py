import os

import pytest_asyncio
from httpx import AsyncClient, ASGITransport

os.environ.setdefault(
    "DATABASE_URL",
    os.getenv("TEST_DATABASE_URL", "postgres://ai_task_manager:change-me@localhost:15432/ai_task_manager"),
)

from main import app
from services import db_service


class FakeDatabase:
    def __init__(self):
        self.users = {}
        self.users_by_id = {}
        self.next_user_id = 1
        self.integrations = {}
        self.tasks = {}
        self.events = {}
        self.sync_state = {}
        self.telegram_links = {}
        self.telegram_codes = {}

    def clear_cache(self):
        self.users = {}
        self.users_by_id = {}
        self.next_user_id = 1
        self.integrations = {}
        self.tasks = {}
        self.events = {}
        self.sync_state = {}
        self.telegram_links = {}
        self.telegram_codes = {}

    def init_db(self):
        return None

    def get_user_by_username(self, username):
        return self.users.get(username)

    def get_user_by_id(self, user_id):
        return self.users_by_id.get(user_id)

    def create_user(self, username, password_hash):
        user = {"id": self.next_user_id, "username": username, "password_hash": password_hash}
        self.next_user_id += 1
        self.users[username] = user
        self.users_by_id[user["id"]] = user
        self.integrations[user["id"]] = {
            "todoist_api_token": None,
            "google_token_json": None,
            "telegram_bot_token": None,
        }
        return user

    def get_integrations(self, user_id, include_secrets=False):
        integrations = self.integrations.get(
            user_id,
            {"todoist_api_token": None, "google_token_json": None, "telegram_bot_token": None},
        )
        if include_secrets:
            return dict(integrations)
        return {
            "todoist_connected": bool(integrations.get("todoist_api_token")),
            "google_connected": bool(integrations.get("google_token_json")),
            "telegram_connected": bool(integrations.get("telegram_bot_token")),
            "updated_at": None,
        }

    def upsert_integrations(self, user_id, todoist_api_token=None, google_token_json=None, telegram_bot_token=None):
        self.integrations[user_id] = {
            "todoist_api_token": todoist_api_token,
            "google_token_json": google_token_json,
            "telegram_bot_token": telegram_bot_token,
        }

    def create_telegram_link_code(self, user_id, ttl_minutes=15):
        code = "ABCD1234"
        self.telegram_codes[code] = user_id
        return {"code": code, "expires_at": "2026-05-17T12:15:00+00:00"}

    def get_telegram_link(self, user_id):
        return self.telegram_links.get(user_id)

    def get_user_by_telegram_id(self, telegram_user_id):
        for user_id, link in self.telegram_links.items():
            if link["telegram_user_id"] == telegram_user_id:
                user = self.users_by_id[user_id]
                return {**user, **link}
        return None

    def consume_telegram_link_code(self, code, telegram_user_id, telegram_username=None):
        user_id = self.telegram_codes.pop(code.strip().upper(), None)
        if not user_id:
            return None
        link = {
            "user_id": user_id,
            "telegram_user_id": telegram_user_id,
            "telegram_username": telegram_username,
            "linked_at": "2026-05-17T12:00:00+00:00",
        }
        self.telegram_links[user_id] = link
        return self.users_by_id[user_id]

    def replace_tasks(self, user_id, tasks):
        self.tasks[user_id] = list(tasks)
        self.sync_state.setdefault(user_id, {})["tasks"] = {"item_count": len(tasks)}

    def get_tasks(self, user_id):
        return list(self.tasks.get(user_id, []))

    def upsert_task(self, user_id, task):
        tasks = [existing for existing in self.tasks.get(user_id, []) if existing["id"] != task["id"]]
        tasks.append(task)
        self.tasks[user_id] = tasks

    def delete_task(self, user_id, task_id):
        self.tasks[user_id] = [t for t in self.tasks.get(user_id, []) if t["id"] != task_id]

    def replace_events(self, user_id, events):
        self.events[user_id] = list(events)
        self.sync_state.setdefault(user_id, {})["events"] = {"item_count": len(events)}

    def get_events(self, user_id):
        return list(self.events.get(user_id, []))

    def upsert_event(self, user_id, event):
        events = [existing for existing in self.events.get(user_id, []) if existing["id"] != event["id"]]
        events.append(event)
        self.events[user_id] = events

    def get_sync_state(self, user_id):
        return self.sync_state.get(user_id, {})


@pytest_asyncio.fixture(autouse=True)
async def fake_database(monkeypatch):
    fake = FakeDatabase()
    for name in (
        "clear_cache",
        "init_db",
        "get_user_by_username",
        "get_user_by_id",
        "create_user",
        "get_integrations",
        "upsert_integrations",
        "create_telegram_link_code",
        "get_telegram_link",
        "get_user_by_telegram_id",
        "consume_telegram_link_code",
        "replace_tasks",
        "get_tasks",
        "upsert_task",
        "delete_task",
        "replace_events",
        "get_events",
        "upsert_event",
        "get_sync_state",
    ):
        monkeypatch.setattr(db_service, name, getattr(fake, name))
    yield fake


@pytest_asyncio.fixture
async def client():
    db_service.clear_cache()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    db_service.clear_cache()
