import pytest
import datetime
import json
from unittest.mock import AsyncMock, patch, MagicMock
from services.scheduler import SchedulerService

@pytest.fixture
def scheduler_service():
    return SchedulerService()

@pytest.mark.asyncio
async def test_generate_smart_schedule_success(scheduler_service):
    from services.scheduler import todoist_service, gcal_service, ai_service
    
    with patch.object(todoist_service, 'get_active_tasks', new_callable=AsyncMock) as mock_tasks, \
         patch.object(gcal_service, 'get_upcoming_events') as mock_events, \
         patch.object(ai_service, 'client') as mock_client:
        
        mock_task = MagicMock()
        mock_task.content = "Fix bug"
        mock_task.priority = 1
        mock_tasks.return_value = [mock_task]
        
        mock_events.return_value = [
            {'summary': 'Meeting', 'start': {'dateTime': '2026-04-26T10:00:00Z'}, 'end': {'dateTime': '2026-04-26T11:00:00Z'}}
        ]
        
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='[{"title": "Fix bug", "start_time": "2026-04-26T11:30:00Z", "end_time": "2026-04-26T12:00:00Z"}]'))
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        schedule = await scheduler_service.generate_smart_schedule()
        assert len(schedule) == 1
        assert schedule[0]['title'] == "Fix bug"

@pytest.mark.asyncio
async def test_generate_smart_schedule_no_tasks(scheduler_service):
    from services.scheduler import todoist_service, gcal_service
    with patch.object(todoist_service, 'get_active_tasks', new_callable=AsyncMock) as mock_tasks, \
         patch.object(gcal_service, 'get_upcoming_events', return_value=[]):
        mock_tasks.return_value = []
        schedule = await scheduler_service.generate_smart_schedule()
        assert schedule == []

@pytest.mark.asyncio
async def test_generate_smart_schedule_no_ai(scheduler_service):
    from services.scheduler import todoist_service, ai_service, gcal_service
    with patch.object(todoist_service, 'get_active_tasks', new_callable=AsyncMock) as mock_tasks, \
         patch.object(gcal_service, 'get_upcoming_events', return_value=[]), \
         patch.object(ai_service, 'client', None):
        mock_tasks.return_value = [MagicMock()]
        schedule = await scheduler_service.generate_smart_schedule()
        assert schedule == []

@pytest.mark.asyncio
async def test_generate_smart_schedule_markdown_cleanup(scheduler_service):
    from services.scheduler import todoist_service, gcal_service, ai_service
    with patch.object(todoist_service, 'get_active_tasks', new_callable=AsyncMock) as mock_tasks, \
         patch.object(gcal_service, 'get_upcoming_events', return_value=[]), \
         patch.object(ai_service, 'client') as mock_client:
        
        mock_tasks.return_value = [MagicMock()]
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='```json\n[]\n```'))
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        schedule = await scheduler_service.generate_smart_schedule()
        assert schedule == []

        # Test with simple markdown
        mock_response.choices[0].message.content = '```\n[]\n```'
        schedule = await scheduler_service.generate_smart_schedule()
        assert schedule == []

@pytest.mark.asyncio
async def test_generate_smart_schedule_error(scheduler_service):
    from services.scheduler import todoist_service, gcal_service, ai_service
    with patch.object(todoist_service, 'get_active_tasks', new_callable=AsyncMock) as mock_tasks, \
         patch.object(gcal_service, 'get_upcoming_events', return_value=[]), \
         patch.object(ai_service, 'client') as mock_client:
        
        mock_tasks.return_value = [MagicMock()]
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("Timeout"))
        
        schedule = await scheduler_service.generate_smart_schedule()
        assert schedule == []

def test_apply_schedule_to_calendar(scheduler_service):
    with patch('services.scheduler.gcal_service') as mock_gcal:
        schedule = [
            {"title": "Fix bug", "start_time": "2026-04-26T11:30:00Z", "end_time": "2026-04-26T12:00:00Z"}
        ]
        scheduler_service.apply_schedule_to_calendar(schedule)
        mock_gcal.create_event.assert_called()

def test_apply_schedule_to_calendar_error(scheduler_service):
    with patch('services.scheduler.gcal_service') as mock_gcal:
        mock_gcal.create_event.side_effect = Exception("Failed")
        scheduler_service.apply_schedule_to_calendar([{"title": "X", "start_time": "invalid", "end_time": "invalid"}])
        # Should not crash
