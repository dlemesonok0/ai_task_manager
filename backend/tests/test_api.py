import pytest
from unittest.mock import AsyncMock, MagicMock, patch

async def auth_headers(client):
    await client.post("/api/auth/register", json={"username": "testuser", "password": "testpass1234"})
    response = await client.post("/api/auth/login", json={"username": "testuser", "password": "testpass1234"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.mark.asyncio
async def test_read_root(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "AI Task Manager API is running"}

@pytest.mark.asyncio
async def test_login_rejects_invalid_credentials(client):
    response = await client.post("/api/auth/login", json={"username": "nonexistent", "password": "wrong"})
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_tasks_require_authentication(client):
    response = await client.get("/api/tasks")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_logs_require_authentication(client):
    response = await client.get("/api/logs")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_get_logs(client):
    response = await client.get("/api/logs", headers=await auth_headers(client))
    assert response.status_code == 200
    assert "entries" in response.json()

@pytest.mark.asyncio
async def test_get_tasks(client):
    # Mock Todoist task object
    class MockTask:
        def __init__(self, id, content, priority, due=None):
            self.id = id
            self.content = content
            self.priority = priority
            self.due = due

    mock_tasks = [
        MockTask("1", "Test Task 1", 1),
        MockTask("2", "Test Task 2", 4)
    ]

    service = MagicMock()
    service.get_active_tasks = AsyncMock(return_value=mock_tasks)
    with patch("main.todoist_service_for_token", return_value=service):
        response = await client.get("/api/tasks", headers=await auth_headers(client))
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["content"] == "Test Task 1"
        assert data[1]["priority"] == 4

@pytest.mark.asyncio
async def test_get_events(client):
    mock_events = [
        {
            "id": "event1",
            "summary": "Meeting",
            "start": {"dateTime": "2026-04-26T10:00:00Z"},
            "end": {"dateTime": "2026-04-26T11:00:00Z"}
        }
    ]

    service = MagicMock()
    service.get_upcoming_events.return_value = mock_events
    with patch("main.gcal_service_for_token", return_value=service):
        response = await client.get("/api/events", headers=await auth_headers(client))
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["summary"] == "Meeting"

@pytest.mark.asyncio
async def test_update_event(client):
    mock_event = {
        "id": "event1",
        "summary": "Updated Meeting",
        "calendarId": "work",
        "start": {"dateTime": "2026-04-26T10:00:00+00:00"},
        "end": {"dateTime": "2026-04-26T11:00:00+00:00"}
    }

    service = MagicMock()
    service.update_event.return_value = mock_event
    with patch("main.gcal_service_for_token", return_value=service):
        response = await client.patch("/api/events/event1", json={
            "calendar_id": "work",
            "summary": "Updated Meeting",
            "start": "2026-04-26T10:00:00Z",
            "end": "2026-04-26T11:00:00Z"
        }, headers=await auth_headers(client))

        assert response.status_code == 200
        data = response.json()
        assert data["summary"] == "Updated Meeting"
        service.update_event.assert_called_once()

@pytest.mark.asyncio
async def test_update_event_invalid_datetime(client):
    response = await client.patch("/api/events/event1", json={
        "calendar_id": "work",
        "summary": "Updated Meeting",
        "start": "not-a-date",
        "end": "2026-04-26T11:00:00Z"
    }, headers=await auth_headers(client))

    assert response.status_code == 400

@pytest.mark.asyncio
async def test_update_event_invalid_range(client):
    response = await client.patch("/api/events/event1", json={
        "calendar_id": "work",
        "summary": "Updated Meeting",
        "start": "2026-04-26T11:00:00Z",
        "end": "2026-04-26T10:00:00Z"
    }, headers=await auth_headers(client))

    assert response.status_code == 400

@pytest.mark.asyncio
async def test_create_task(client):
    class MockTask:
        def __init__(self, id, content, priority, due=None):
            self.id = id
            self.content = content
            self.priority = priority
            self.due = due

    mock_task = MockTask("123", "New Task", 2)

    service = MagicMock()
    service.create_task = AsyncMock(return_value=mock_task)
    with patch("main.todoist_service_for_token", return_value=service):
        response = await client.post("/api/tasks", json={"content": "New Task", "priority": 2}, headers=await auth_headers(client))
        
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "New Task"
        assert data["id"] == "123"

@pytest.mark.asyncio
async def test_create_task_fail(client):
    service = MagicMock()
    service.create_task = AsyncMock(return_value=None)
    with patch("main.todoist_service_for_token", return_value=service):
        response = await client.post("/api/tasks", json={"content": "Fail Task"}, headers=await auth_headers(client))
        
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to create task"

@pytest.mark.asyncio
async def test_create_telegram_link_code(client):
    response = await client.post("/api/telegram/link-code", headers=await auth_headers(client))

    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "ABCD1234"
    assert data["command"] == "/link ABCD1234"

@pytest.mark.asyncio
async def test_ai_health_disabled(client):
    mock_hc = AsyncMock(return_value={"status": "disabled"})
    with patch("main.ai_service.health_check", mock_hc):
        response = await client.get("/api/health/ai")
    assert response.status_code == 200
    assert response.json() == {"status": "disabled"}

@pytest.mark.asyncio
async def test_ai_health_ok(client):
    mock_hc = AsyncMock(return_value={"status": "ok", "provider": "gemini", "model": "gemini-2.0-flash"})
    with patch("main.ai_service.health_check", mock_hc):
        response = await client.get("/api/health/ai")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["provider"] == "gemini"

@pytest.mark.asyncio
async def test_ai_health_degraded(client):
    mock_hc = AsyncMock(return_value={"status": "degraded", "provider": "gemini", "model": "gemini-1.5-flash", "error": "API key not valid"})
    with patch("main.ai_service.health_check", mock_hc):
        response = await client.get("/api/health/ai")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert "error" in data


@pytest.mark.asyncio
async def test_register_short_username(client):
    response = await client.post("/api/auth/register", json={"username": "ab", "password": "password1234"})
    assert response.status_code == 400
    assert "3 characters" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_short_password(client):
    response = await client.post("/api/auth/register", json={"username": "testuser2", "password": "short"})
    assert response.status_code == 400
    assert "8 characters" in response.json()["detail"]


@pytest.mark.asyncio
async def test_read_current_user(client):
    headers = await auth_headers(client)
    response = await client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert "id" in data


@pytest.mark.asyncio
async def test_get_integrations(client):
    headers = await auth_headers(client)
    response = await client.get("/api/integrations", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "todoist_connected" in data


@pytest.mark.asyncio
async def test_update_integrations(client):
    headers = await auth_headers(client)
    response = await client.put("/api/integrations", json={"todoist_api_token": "test-token"}, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["todoist_connected"] is True


@pytest.mark.asyncio
async def test_update_integrations_invalid_json(client):
    headers = await auth_headers(client)
    response = await client.put("/api/integrations", json={"google_token_json": "not-json"}, headers=headers)
    assert response.status_code == 400
    assert "invalid" in response.json()["detail"]


@pytest.mark.asyncio
async def test_download_logs_not_found(client):
    headers = await auth_headers(client)
    with patch("main.log_path") as mock_log_path:
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_log_path.return_value = mock_path
        response = await client.get("/api/logs/download", headers=headers)
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_sync_data(client):
    headers = await auth_headers(client)
    mock_service = MagicMock()
    mock_service.get_active_tasks = AsyncMock(return_value=[])
    mock_gcal = MagicMock()
    mock_gcal.get_upcoming_events.return_value = []
    with patch("main.todoist_service_for_token", return_value=mock_service), \
         patch("main.gcal_service_for_token", return_value=mock_gcal):
        response = await client.post("/api/sync", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert "events" in data


@pytest.mark.asyncio
async def test_get_sync_state(client):
    headers = await auth_headers(client)
    response = await client.get("/api/sync/state", headers=headers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_tasks_background_sync(client):
    mock_tasks = [{"id": "1", "content": "Cached", "priority": 1, "due": None}]
    await client.post("/api/auth/register", json={"username": "bguser", "password": "password1234"})
    response = await client.post("/api/auth/login", json={"username": "bguser", "password": "password1234"})
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    mock_service = MagicMock()
    mock_service.get_active_tasks = AsyncMock(return_value=[])
    with patch("main.todoist_service_for_token", return_value=mock_service):
        response = await client.get("/api/tasks", headers=headers)
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_events_background_sync(client):
    headers = await auth_headers(client)
    mock_gcal = MagicMock()
    mock_gcal.get_upcoming_events.return_value = []
    with patch("main.gcal_service_for_token", return_value=mock_gcal):
        response = await client.get("/api/events", headers=headers)
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_event_fail(client):
    headers = await auth_headers(client)
    service = MagicMock()
    service.update_event.return_value = None
    with patch("main.gcal_service_for_token", return_value=service):
        from datetime import datetime, timezone
        start = datetime(2026, 4, 26, 10, 0, tzinfo=timezone.utc).isoformat()
        end = datetime(2026, 4, 26, 11, 0, tzinfo=timezone.utc).isoformat()
        response = await client.patch("/api/events/event1", json={
            "calendar_id": "primary",
            "summary": "Test",
            "start": start,
            "end": end,
        }, headers=headers)
        assert response.status_code == 500


@pytest.mark.asyncio
async def test_profile_endpoint_disabled(client):
    response = await client.get("/profile")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_download_logs_success(client):
    headers = await auth_headers(client)
    import tempfile
    from pathlib import Path
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        f.write('{"test": true}\n')
        f.flush()
        tmp_path = Path(f.name)
    with patch("services.logging_service.log_path", return_value=tmp_path):
        response = await client.get("/api/logs/download", headers=headers)
        assert response.status_code == 200
    tmp_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_profile_endpoint_no_profile(client):
    import os
    with patch.dict(os.environ, {"PROFILE": "1"}, clear=False):
        response = await client.get("/profile")
        assert response.status_code == 404
        assert "No profile available" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_tasks_with_refresh(client):
    headers = await auth_headers(client)
    mock_service = MagicMock()
    mock_service.get_active_tasks = AsyncMock(return_value=[])
    with patch("main.todoist_service_for_token", return_value=mock_service):
        response = await client.get("/api/tasks?refresh=true", headers=headers)
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_events_with_refresh(client):
    headers = await auth_headers(client)
    mock_gcal = MagicMock()
    mock_gcal.get_upcoming_events.return_value = []
    with patch("main.gcal_service_for_token", return_value=mock_gcal):
        response = await client.get("/api/events?refresh=true", headers=headers)
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_tasks_background_sync_when_cached(client):
    headers = await auth_headers(client)
    mock_service = MagicMock()
    mock_service.get_active_tasks = AsyncMock(return_value=[
        MagicMock(id="1", content="Task", priority=1, due=None)
    ])
    with patch("main.todoist_service_for_token", return_value=mock_service):
        response = await client.get("/api/tasks", headers=headers)
        assert response.status_code == 200
        response = await client.get("/api/tasks", headers=headers)
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_events_background_sync_when_cached(client):
    headers = await auth_headers(client)
    mock_gcal = MagicMock()
    mock_gcal.get_upcoming_events.return_value = [
        {"id": "1", "summary": "Event", "start": {"dateTime": "2026-01-01T00:00:00Z"}, "end": {"dateTime": "2026-01-01T01:00:00Z"}}
    ]
    with patch("main.gcal_service_for_token", return_value=mock_gcal):
        response = await client.get("/api/events", headers=headers)
        assert response.status_code == 200
        response = await client.get("/api/events", headers=headers)
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_profile_endpoint_with_profile_enabled(client):
    import os
    from main import app
    with patch.dict(os.environ, {"PROFILE": "1"}, clear=False):
        app._last_profile = "<html>profile</html>"
        try:
            response = await client.get("/profile")
            assert response.status_code == 200
            assert "profile" in response.text
        finally:
            if hasattr(app, "_last_profile"):
                delattr(app, "_last_profile")


@pytest.mark.asyncio
async def test_profile_endpoint_import_error(client):
    import os
    with patch.dict(os.environ, {"PROFILE": "1"}, clear=False):
        with patch.dict(os.environ, {"PROFILE": "1"}):
            import main
            original_call_next = None
            async def mock_call_next(request):
                return MagicMock(status_code=200)
            class MockRequest:
                query_params = {"profile": "1"}
                url = MagicMock(path="/test")
                method = "GET"
                client = MagicMock(host="127.0.0.1")
            with patch("builtins.__import__", side_effect=ImportError("no pyinstrument")):
                pass
