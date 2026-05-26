import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from services.todoist_service import TodoistService

@pytest.fixture
def todoist_service():
    with patch('services.todoist_service.TodoistAPIAsync') as mock_api:
        service = TodoistService()
        service.api = mock_api.return_value
        return service

@pytest.mark.asyncio
async def test_get_active_tasks_success(todoist_service):
    # Mock AsyncResultsPaginator
    class MockAsyncPaginator:
        def __init__(self, pages):
            self.pages = pages
            self.index = 0
        def __aiter__(self):
            return self
        async def __anext__(self):
            if self.index >= len(self.pages):
                raise StopAsyncIteration
            page = self.pages[self.index]
            self.index += 1
            return page

    mock_paginator = MockAsyncPaginator([["task1", "task2"]])
    todoist_service.api.get_tasks = AsyncMock(return_value=mock_paginator)
    
    tasks = await todoist_service.get_active_tasks()
    assert len(tasks) == 2
    assert tasks[0] == "task1"

@pytest.mark.asyncio
async def test_get_active_tasks_list_return(todoist_service):
    # Case where get_tasks returns a list directly
    todoist_service.api.get_tasks = AsyncMock(return_value=["task1"])
    tasks = await todoist_service.get_active_tasks()
    assert tasks == ["task1"]

@pytest.mark.asyncio
async def test_get_active_tasks_error(todoist_service):
    todoist_service.api.get_tasks = AsyncMock(side_effect=Exception("API Error"))
    tasks = await todoist_service.get_active_tasks()
    assert tasks == []

@pytest.mark.asyncio
async def test_create_task_success(todoist_service):
    mock_task = MagicMock()
    todoist_service.api.add_task = AsyncMock(return_value=mock_task)
    
    task = await todoist_service.create_task("New Task", "today", 2)
    assert task == mock_task
    todoist_service.api.add_task.assert_called_with(content="New Task", due_string="today", priority=2)

@pytest.mark.asyncio
async def test_create_task_without_due_string(todoist_service):
    mock_task = MagicMock()
    todoist_service.api.add_task = AsyncMock(return_value=mock_task)

    task = await todoist_service.create_task("Inbox Task")

    assert task == mock_task
    todoist_service.api.add_task.assert_called_with(content="Inbox Task", priority=1)

@pytest.mark.asyncio
async def test_create_inbox_task(todoist_service):
    with patch.object(todoist_service, 'create_task', new_callable=AsyncMock) as mock_create:
        mock_create.return_value = MagicMock()

        await todoist_service.create_inbox_task("Inbox Task")

        mock_create.assert_called_once_with(content="Inbox Task", due_string=None, priority=1)

@pytest.mark.asyncio
async def test_create_task_error(todoist_service):
    todoist_service.api.add_task = AsyncMock(side_effect=Exception("Error"))
    task = await todoist_service.create_task("New Task")
    assert task is None

@pytest.mark.asyncio
async def test_close_task_success(todoist_service):
    todoist_service.api.close_task = AsyncMock(return_value=True)
    result = await todoist_service.close_task("123")
    assert result is True

@pytest.mark.asyncio
async def test_close_task_error(todoist_service):
    todoist_service.api.close_task = AsyncMock(side_effect=Exception("Error"))
    result = await todoist_service.close_task("123")
    assert result is False

def test_todoist_service_no_token():
    from services.todoist_service import TodoistService
    service = TodoistService()
    assert service.api is None


def test_todoist_service_with_token():
    with patch('services.todoist_service.TodoistAPIAsync') as mock_api:
        service = TodoistService(token="test_token")
        mock_api.assert_called_once_with("test_token")
        assert service.api is not None


def test_todoist_service_for_token():
    from services.todoist_service import todoist_service_for_token
    with patch('services.todoist_service.TodoistAPIAsync'):
        service = todoist_service_for_token("some_token")
        assert isinstance(service, TodoistService)
        assert service.api is not None

@pytest.mark.asyncio
async def test_methods_no_api():
    service = TodoistService()
    service.api = None
    assert await service.get_active_tasks() == []
    assert await service.create_task("test") is None
    assert await service.create_inbox_task("test") is None
    assert await service.close_task("1") is False
