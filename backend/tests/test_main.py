import pytest
import os
import builtins
from unittest.mock import MagicMock, patch


def test_initialize_database():
    from main import initialize_database
    initialize_database()


@pytest.mark.asyncio
async def test_log_requests_exception():
    from main import log_requests

    request = MagicMock()
    request.method = "GET"
    request.url.path = "/test"
    request.client.host = "127.0.0.1"

    async def broken_call_next(req):
        raise ValueError("test error")

    with pytest.raises(ValueError):
        await log_requests(request, broken_call_next)


@pytest.mark.asyncio
async def test_profile_requests_enabled(client):
    with patch.dict(os.environ, {"PROFILE": "1"}):
        response = await client.get("/?profile=1")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_profile_requests_import_error(client):
    _real_import = builtins.__import__

    def _mock_import(name, *args, **kwargs):
        if name == "pyinstrument":
            raise ImportError("no pyinstrument")
        return _real_import(name, *args, **kwargs)

    with patch("builtins.__import__", _mock_import):
        with patch.dict(os.environ, {"PROFILE": "1"}):
            response = await client.get("/?profile=1")
            assert response.status_code == 200


@pytest.mark.asyncio
async def test_log_requests_exception_middleware(client):
    with patch.dict(os.environ, {"PROFILE": "1"}):
        with patch("pyinstrument.Profiler.start", side_effect=ValueError("profiler failed")):
            with pytest.raises(ValueError):
                await client.get("/?profile=1")