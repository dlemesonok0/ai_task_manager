import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_read_root(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "AI Task Manager API is running"}

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
        response = await client.get("/api/tasks")
        
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
        response = await client.get("/api/events")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["summary"] == "Meeting"
