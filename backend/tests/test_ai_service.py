import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from services.ai_service import AIService

@pytest.fixture
def ai_service():
    with patch('services.ai_service.AsyncOpenAI') as mock_openai:
        service = AIService()
        service.client = mock_openai.return_value
        return service

@pytest.mark.asyncio
async def test_parse_task_nlp_success(ai_service):
    # Mock OpenAI response
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='{"content": "Buy Milk", "due_string": "tomorrow", "priority": 3}'))
    ]
    ai_service.client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    result = await ai_service.parse_task_nlp("Remind me to buy milk tomorrow")
    assert result["content"] == "Buy Milk"
    assert result["due_string"] == "tomorrow"
    assert result["priority"] == 3

@pytest.mark.asyncio
async def test_parse_task_nlp_with_markdown(ai_service):
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='```json\n{"content": "Clean", "due_string": "today", "priority": 1}\n```'))
    ]
    ai_service.client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    result = await ai_service.parse_task_nlp("Clean house")
    assert result["content"] == "Clean"

@pytest.mark.asyncio
async def test_parse_task_nlp_with_simple_markdown(ai_service):
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='```\n{"content": "Simple", "due_string": "today", "priority": 1}\n```'))
    ]
    ai_service.client.chat.completions.create = AsyncMock(return_value=mock_response)
    
    result = await ai_service.parse_task_nlp("Simple task")
    assert result["content"] == "Simple"


@pytest.mark.asyncio
async def test_parse_task_nlp_error(ai_service):
    ai_service.client.chat.completions.create = AsyncMock(side_effect=Exception("LLM Down"))
    
    result = await ai_service.parse_task_nlp("Any text")
    assert result["content"] == "Any text"
    assert result["due_string"] == "today"
    assert result["priority"] == 1

@pytest.mark.asyncio
async def test_parse_task_nlp_no_client():
    service = AIService()
    service.client = None
    result = await service.parse_task_nlp("test")
    assert result["content"] == "test"

def test_ai_service_init_gemini():
    with patch.dict('os.environ', {'GEMINI_API_KEY': 'some_key'}):
        with patch('services.ai_service.AsyncOpenAI') as mock_openai:
            service = AIService()
            assert service.model == "gemini-2.0-flash"

def test_ai_service_init_openai():
    with patch.dict('os.environ', {'GEMINI_API_KEY': '', 'OPENAI_API_KEY': 'sk-test'}):
        with patch('services.ai_service.AsyncOpenAI') as mock_openai:
            service = AIService()
            assert service.model == "gpt-4.1-mini"

def test_ai_service_init_local():
    with patch.dict('os.environ', {'GEMINI_API_KEY': '', 'OPENAI_API_KEY': '', 'LLM_BASE_URL': 'http://local:11434'}):
        with patch('services.ai_service.AsyncOpenAI') as mock_openai:
            service = AIService()
            assert service.model == "llama3"

def test_ai_service_init_none():
    with patch.dict('os.environ', {'GEMINI_API_KEY': '', 'OPENAI_API_KEY': '', 'LLM_BASE_URL': ''}):
        service = AIService()
        assert service.client is None
