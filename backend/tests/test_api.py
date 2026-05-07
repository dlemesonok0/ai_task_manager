import pytest
from unittest.mock import AsyncMock, patch

async def auth_headers(client):
    response = await client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
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
    response = await client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
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

    with patch("services.todoist_service.todoist_service.get_active_tasks", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_tasks
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

    with patch("services.gcal_service.gcal_service.get_upcoming_events") as mock_get:
        mock_get.return_value = mock_events
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

    with patch("services.gcal_service.gcal_service.update_event") as mock_update:
        mock_update.return_value = mock_event
        response = await client.patch("/api/events/event1", json={
            "calendar_id": "work",
            "summary": "Updated Meeting",
            "start": "2026-04-26T10:00:00Z",
            "end": "2026-04-26T11:00:00Z"
        }, headers=await auth_headers(client))

        assert response.status_code == 200
        data = response.json()
        assert data["summary"] == "Updated Meeting"
        mock_update.assert_called_once()

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

    with patch("services.todoist_service.todoist_service.create_task", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_task
        response = await client.post("/api/tasks", json={"content": "New Task", "priority": 2}, headers=await auth_headers(client))
        
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "New Task"
        assert data["id"] == "123"

@pytest.mark.asyncio
async def test_create_task_fail(client):
    with patch("services.todoist_service.todoist_service.create_task", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = None
        response = await client.post("/api/tasks", json={"content": "Fail Task"}, headers=await auth_headers(client))
        
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to create task"
