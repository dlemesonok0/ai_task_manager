import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from bot import command_start_handler, command_help_handler, command_briefing_handler, command_autoschedule_handler, text_handler

@pytest.fixture
def mock_message():
    message = AsyncMock()
    message.from_user.full_name = "Test User"
    message.text = "Test message"
    message.answer = AsyncMock()
    return message

@pytest.mark.asyncio
async def test_command_start(mock_message):
    await command_start_handler(mock_message)
    mock_message.answer.assert_called()
    assert "Привет" in mock_message.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_command_help(mock_message):
    await command_help_handler(mock_message)
    mock_message.answer.assert_called()
    assert "Как мной пользоваться" in mock_message.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_command_briefing(mock_message):
    with patch('bot.todoist_service') as mock_todoist:
        mock_todoist.get_active_tasks = AsyncMock(return_value=[MagicMock(content="Task 1", priority=1)])
        await command_briefing_handler(mock_message)
        mock_message.answer.assert_called()
        assert "Task 1" in mock_message.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_command_briefing_empty(mock_message):
    with patch('bot.todoist_service') as mock_todoist:
        mock_todoist.get_active_tasks = AsyncMock(return_value=[])
        await command_briefing_handler(mock_message)
        mock_message.answer.assert_called_with("You have no active tasks for today. Enjoy your day!")

@pytest.mark.asyncio
async def test_command_autoschedule(mock_message):
    with patch('bot.scheduler_service') as mock_scheduler:
        mock_scheduler.generate_smart_schedule = AsyncMock(return_value=[{"title": "S", "start_time": "10:00", "end_time": "11:00"}])
        
        status_msg = AsyncMock()
        mock_message.answer.return_value = status_msg
        
        await command_autoschedule_handler(mock_message)
        mock_scheduler.apply_schedule_to_calendar.assert_called()
        assert "Your AI Schedule" in mock_message.answer.call_args_list[1][0][0]

@pytest.mark.asyncio
async def test_command_autoschedule_fail(mock_message):
    with patch('bot.scheduler_service') as mock_scheduler:
        mock_scheduler.generate_smart_schedule = AsyncMock(return_value=[])
        
        status_msg = AsyncMock()
        mock_message.answer.return_value = status_msg
        
        await command_autoschedule_handler(mock_message)
        status_msg.edit_text.assert_called_with("❌ Could not generate a schedule. Ensure you have active tasks and AI configured.")

@pytest.mark.asyncio
async def test_text_handler(mock_message):
    with patch('bot.ai_service') as mock_ai, \
         patch('bot.todoist_service') as mock_todoist:
        
        mock_ai.parse_task_nlp = AsyncMock(return_value={"content": "New", "due_string": "today", "priority": 1})
        mock_todoist.create_task = AsyncMock(return_value=MagicMock(content="New"))
        
        status_msg = AsyncMock()
        mock_message.answer.return_value = status_msg
        
        await text_handler(mock_message)
        mock_todoist.create_task.assert_called()
        status_msg.edit_text.assert_called()
        assert "Task created" in status_msg.edit_text.call_args[0][0]

@pytest.mark.asyncio
async def test_text_handler_fail(mock_message):
    with patch('bot.ai_service') as mock_ai, \
         patch('bot.todoist_service') as mock_todoist:
        
        mock_ai.parse_task_nlp = AsyncMock(return_value={})
        mock_todoist.create_task = AsyncMock(return_value=None)
        
        status_msg = AsyncMock()
        mock_message.answer.return_value = status_msg
        
        await text_handler(mock_message)
        status_msg.edit_text.assert_called_with("❌ Failed to create task in Todoist. Check your API token.")
