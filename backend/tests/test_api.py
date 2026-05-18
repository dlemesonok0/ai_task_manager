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
