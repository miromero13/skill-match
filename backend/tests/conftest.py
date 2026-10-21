import pytest
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.main import app
from app.db.session import get_db

class MockAsyncSession:
    """Mock de sesión asíncrona de SQLAlchemy para pruebas unitarias sin PostgreSQL externo."""
    async def execute(self, statement, *args, **kwargs):
        class MockResult:
            def scalar(self):
                return 1
        return MockResult()

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def close(self):
        pass

async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    mock_session = MockAsyncSession()
    yield mock_session

@pytest.fixture
def test_app():
    """Retorna la aplicación con dependencias overrideadas para testing."""
    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()

@pytest.fixture
async def client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """Cliente HTTP asíncrono configurado contra la app FastAPI."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
