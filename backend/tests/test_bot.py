import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from bot import (
    command_start_handler,
    command_help_handler,
    command_link_handler,
    command_inbox_handler,
    command_briefing_handler,
    command_autoschedule_handler,
    text_handler,
    _link_telegram_account,
    _linked_context,
)

@pytest.fixture
def mock_message():
    message = AsyncMock()
    message.from_user.id = 1001
    message.from_user.username = "test_user"
    message.from_user.full_name = "Test User"
    message.text = "Test message"
    message.answer = AsyncMock()
    return message

@pytest.mark.asyncio
async def test_command_start(mock_message):
    mock_message.text = "/start"
    await command_start_handler(mock_message)
    mock_message.answer.assert_called()
    assert "Привет" in mock_message.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_command_help(mock_message):
    await command_help_handler(mock_message)
    mock_message.answer.assert_called()
    assert "Как мной пользоваться" in mock_message.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_command_link(mock_message):
    mock_message.text = "/link ABCD1234"
    with patch('bot.db_service') as mock_db:
        mock_db.consume_telegram_link_code.return_value = {"id": 1, "username": "admin"}

        await command_link_handler(mock_message)

        mock_db.consume_telegram_link_code.assert_called_once_with(
            code="ABCD1234",
            telegram_user_id=1001,
            telegram_username="test_user",
        )
        mock_message.answer.assert_called()
        assert "привязан" in mock_message.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_command_inbox(mock_message):
    mock_message.text = "/inbox Buy milk"
    with patch('bot.db_service') as mock_db, patch('bot.todoist_service_for_token') as service_factory:
        mock_db.get_user_by_telegram_id.return_value = {"id": 1, "username": "admin"}
        mock_db.get_integrations.return_value = {"todoist_api_token": "token"}
        mock_todoist = MagicMock()
        service_factory.return_value = mock_todoist
        mock_todoist.create_inbox_task = AsyncMock(return_value=MagicMock(content="Buy milk"))

        await command_inbox_handler(mock_message)

        mock_todoist.create_inbox_task.assert_called_once_with("Buy milk")
        mock_message.answer.assert_called()
        assert "Added to Inbox" in mock_message.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_command_inbox_empty(mock_message):
    mock_message.text = "/inbox"

    await command_inbox_handler(mock_message)

    mock_message.answer.assert_called_with("Напиши задачу после команды: /inbox купить молоко")

@pytest.mark.asyncio
async def test_command_inbox_fail(mock_message):
    mock_message.text = "/inbox Buy milk"
    with patch('bot.db_service') as mock_db, patch('bot.todoist_service_for_token') as service_factory:
        mock_db.get_user_by_telegram_id.return_value = {"id": 1, "username": "admin"}
        mock_db.get_integrations.return_value = {"todoist_api_token": "token"}
        mock_todoist = MagicMock()
        service_factory.return_value = mock_todoist
        mock_todoist.create_inbox_task = AsyncMock(return_value=None)

        await command_inbox_handler(mock_message)

        mock_message.answer.assert_called_with("❌ Failed to create task in Todoist Inbox. Check your API token.")

@pytest.mark.asyncio
async def test_command_briefing(mock_message):
    with patch('bot.db_service') as mock_db, patch('bot.todoist_service_for_token') as service_factory:
        mock_db.get_user_by_telegram_id.return_value = {"id": 1, "username": "admin"}
        mock_db.get_integrations.return_value = {"todoist_api_token": "token"}
        mock_todoist = MagicMock()
        service_factory.return_value = mock_todoist
        mock_todoist.get_active_tasks = AsyncMock(return_value=[MagicMock(content="Task 1", priority=1)])
        await command_briefing_handler(mock_message)
        mock_message.answer.assert_called()
        assert "Task 1" in mock_message.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_command_briefing_empty(mock_message):
    with patch('bot.db_service') as mock_db, patch('bot.todoist_service_for_token') as service_factory:
        mock_db.get_user_by_telegram_id.return_value = {"id": 1, "username": "admin"}
        mock_db.get_integrations.return_value = {"todoist_api_token": "token"}
        mock_todoist = MagicMock()
        service_factory.return_value = mock_todoist
        mock_todoist.get_active_tasks = AsyncMock(return_value=[])
        await command_briefing_handler(mock_message)
        mock_message.answer.assert_called_with("You have no active tasks for today. Enjoy your day!")

@pytest.mark.asyncio
async def test_command_autoschedule(mock_message):
    await command_autoschedule_handler(mock_message)
    assert "web-сценарии" in mock_message.answer.call_args[0][0]

@pytest.mark.asyncio
async def test_command_autoschedule_fail(mock_message):
    await command_autoschedule_handler(mock_message)
    mock_message.answer.assert_called()

@pytest.mark.asyncio
async def test_text_handler(mock_message):
    with patch('bot.ai_service') as mock_ai, \
         patch('bot.db_service') as mock_db, \
         patch('bot.todoist_service_for_token') as service_factory:
        
        mock_db.get_user_by_telegram_id.return_value = {"id": 1, "username": "admin"}
        mock_db.get_integrations.return_value = {"todoist_api_token": "token"}
        mock_todoist = MagicMock()
        service_factory.return_value = mock_todoist
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
         patch('bot.db_service') as mock_db, \
         patch('bot.todoist_service_for_token') as service_factory:
        
        mock_db.get_user_by_telegram_id.return_value = {"id": 1, "username": "admin"}
        mock_db.get_integrations.return_value = {"todoist_api_token": "token"}
        mock_todoist = MagicMock()
        service_factory.return_value = mock_todoist
        mock_ai.parse_task_nlp = AsyncMock(return_value={})
        mock_todoist.create_task = AsyncMock(return_value=None)
        
        status_msg = AsyncMock()
        mock_message.answer.return_value = status_msg
        
        await text_handler(mock_message)
        status_msg.edit_text.assert_called_with("❌ Failed to create task in Todoist. Check your API token.")


@pytest.mark.asyncio
async def test_link_telegram_no_user_id():
    message = AsyncMock()
    message.from_user = None
    message.answer = AsyncMock()
    await _link_telegram_account(message, "CODE123")
    message.answer.assert_called_with("Не удалось определить Telegram user id. Попробуй еще раз позже.")


@pytest.mark.asyncio
async def test_link_telegram_invalid_code():
    message = AsyncMock()
    message.from_user.id = 1001
    message.from_user.username = "test"
    message.from_user.full_name = "Test"
    message.answer = AsyncMock()
    with patch('bot.db_service') as mock_db:
        mock_db.consume_telegram_link_code.return_value = None
        await _link_telegram_account(message, "CODE123")
        message.answer.assert_called_with("Код привязки не найден или уже истек. Создай новый код в web-интерфейсе.")


@pytest.mark.asyncio
async def test_linked_context_no_user_id():
    message = AsyncMock()
    message.from_user = None
    message.answer = AsyncMock()
    result = await _linked_context(message)
    assert result is None
    message.answer.assert_called_with("Не удалось определить Telegram user id. Попробуй еще раз позже.")


@pytest.mark.asyncio
async def test_linked_context_not_linked():
    message = AsyncMock()
    message.from_user.id = 1001
    message.from_user.username = "test"
    message.from_user.full_name = "Test"
    message.answer = AsyncMock()
    with patch('bot.db_service') as mock_db:
        mock_db.get_user_by_telegram_id.return_value = None
        result = await _linked_context(message)
        assert result is None
        message.answer.assert_called()
        assert "привяжи" in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_linked_context_no_todoist():
    message = AsyncMock()
    message.from_user.id = 1001
    message.from_user.username = "test"
    message.from_user.full_name = "Test"
    message.answer = AsyncMock()
    with patch('bot.db_service') as mock_db:
        mock_db.get_user_by_telegram_id.return_value = {"id": 1, "username": "admin"}
        mock_db.get_integrations.return_value = {"todoist_api_token": None}
        result = await _linked_context(message)
        assert result is None
        message.answer.assert_called()
        assert "Todoist" in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_command_start_with_link_code():
    message = AsyncMock()
    message.text = "/start CODE123"
    message.from_user.id = 1001
    message.from_user.username = "test"
    message.from_user.full_name = "Test"
    message.answer = AsyncMock()
    with patch('bot.db_service') as mock_db:
        mock_db.consume_telegram_link_code.return_value = {"id": 1, "username": "admin"}
        await command_start_handler(message)
        mock_db.consume_telegram_link_code.assert_called()
        message.answer.assert_called()
        assert "привязан" in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_command_link_no_code():
    message = AsyncMock()
    message.text = "/link"
    message.answer = AsyncMock()
    await command_link_handler(message)
    message.answer.assert_called_with("Напиши код после команды: /link ABCD1234")


@pytest.mark.asyncio
async def test_command_inbox_no_context():
    message = AsyncMock()
    message.text = "/inbox test"
    message.from_user.id = 1001
    message.from_user.username = "test"
    message.from_user.full_name = "Test"
    message.answer = AsyncMock()
    with patch('bot.db_service') as mock_db:
        mock_db.get_user_by_telegram_id.return_value = None
        await command_inbox_handler(message)
        message.answer.assert_called()


@pytest.mark.asyncio
async def test_command_briefing_no_context():
    message = AsyncMock()
    message.from_user.id = 1001
    message.from_user.username = "test"
    message.from_user.full_name = "Test"
    message.answer = AsyncMock()
    with patch('bot.db_service') as mock_db:
        mock_db.get_user_by_telegram_id.return_value = None
        await command_briefing_handler(message)
        message.answer.assert_called()


@pytest.mark.asyncio
async def test_text_handler_no_context():
    message = AsyncMock()
    message.text = "Some task"
    message.from_user.id = 1001
    message.from_user.username = "test"
    message.from_user.full_name = "Test"
    message.answer = AsyncMock()
    with patch('bot.db_service') as mock_db:
        mock_db.get_user_by_telegram_id.return_value = None
        await text_handler(message)
        message.answer.assert_called()
