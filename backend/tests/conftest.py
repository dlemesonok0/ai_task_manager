import os

import pytest_asyncio
from httpx import AsyncClient, ASGITransport

os.environ.setdefault("DATABASE_PATH", "data/test_app.db")

from main import app
from services import db_service

@pytest_asyncio.fixture
async def client():
    db_service.clear_cache()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    db_service.clear_cache()
